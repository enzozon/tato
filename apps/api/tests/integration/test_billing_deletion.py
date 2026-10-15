from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app import account_service, billing_cleanup, billing_events
from app.auth import Identity
from app.billing_database import billing_account_session
from app.billing_resolution import SubscriptionReference
from app.billing_stripe import StripeSandbox
from app.models import BillingCheckout, Subscription, User
from tests.integration.test_billing_database_runtime import billing_runtime as billing_runtime

pytestmark = pytest.mark.integration


@pytest.fixture
def deletion_fixture(runtime_engine, billing_runtime, owners, monkeypatch):
    owner, _ = owners
    request_id = uuid4()
    with billing_account_session(billing_runtime, owner) as session:
        session.add(
            Subscription(
                user_id=owner,
                billing_provider="stripe",
                external_id="sub_demo",
                external_customer_id="cus_demo",
                plan="pro",
            )
        )
        session.add(
            BillingCheckout(
                user_id=owner,
                provider="stripe",
                request_id=request_id,
                external_id="cs_test_demo",
                amount_cents=3900,
                status="paid",
            )
        )
    checkout = {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_demo",
        "subscription": "sub_demo",
    }
    deleted, calls = [], []

    def transport(request):
        calls.append(request.method + " " + request.url.path)
        if "checkout/sessions" in request.url.path:
            return httpx.Response(200, json=checkout)
        if request.method == "DELETE":
            deleted.append(True)
        return httpx.Response(
            200,
            json={
                "id": "cus_demo",
                "object": "customer",
                **({"deleted": True} if deleted else {"livemode": False}),
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_demo", client, "https://tato.example/")
        monkeypatch.setattr(billing_cleanup, "provider_for", lambda client: provider)
        monkeypatch.setattr(account_service, "check_rate", lambda *args: None)
        monkeypatch.setattr(account_service, "clear_rate", lambda *args: None)
        monkeypatch.setattr(account_service, "clear_configured_cache", lambda *args: None)
        yield provider, SubscriptionReference(owner, request_id, "sub_demo", "cus_demo"), calls


def test_remote_cleanup_before_supabase_failure_keeps_marker_and_retries_tombstone(
    runtime_engine, admin_engine, deletion_fixture, monkeypatch
):
    provider, reference, calls = deletion_fixture

    def unavailable(owner):
        assert "DELETE /v1/customers/cus_demo" in calls
        raise HTTPException(503)

    monkeypatch.setattr(account_service, "delete_identity", unavailable)
    with pytest.raises(HTTPException):
        account_service.request_deletion(
            runtime_engine, reference.owner, lambda: Identity(id=reference.owner)
        )
    with Session(admin_engine) as session:
        assert session.get(User, reference.owner).deletion_requested_at is not None
        assert (
            session.exec(select(BillingCheckout).where(BillingCheckout.user_id == reference.owner))
            .one()
            .external_id
            == "cs_test_demo"
        )
    monkeypatch.setattr(account_service, "delete_identity", lambda owner: None)
    account_service.finish_deletion(runtime_engine, reference.owner)
    assert calls.count("DELETE /v1/customers/cus_demo") == 1
    with Session(admin_engine) as session:
        assert session.get(User, reference.owner) is None


def test_webhook_waiting_for_deletion_does_not_recreate_or_reactivate(
    runtime_engine, billing_runtime, admin_engine, deletion_fixture, monkeypatch
):
    provider, reference, calls = deletion_fixture
    entered, release, started = Event(), Event(), Event()

    def delete_identity(owner):
        entered.set()
        assert release.wait(4)

    monkeypatch.setattr(account_service, "delete_identity", delete_identity)
    monkeypatch.setattr(billing_events, "resolve_subscription", lambda *args: reference)

    def webhook():
        started.set()
        return billing_events.process_event(
            billing_runtime, provider, "evt_delete_race", "invoice.paid", "in_demo"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(
            account_service.request_deletion,
            runtime_engine,
            reference.owner,
            lambda: Identity(id=reference.owner),
        )
        assert entered.wait(4)
        event = pool.submit(webhook)
        assert started.wait(4)
        release.set()
        deletion.result(timeout=5)
        assert event.result(timeout=5) is False
    with Session(admin_engine) as session:
        assert session.get(User, reference.owner) is None


def test_cleanup_failure_preserves_identity_and_sql_bindings(
    runtime_engine, admin_engine, deletion_fixture, monkeypatch
):
    provider, reference, _ = deletion_fixture
    identity = Mock()
    monkeypatch.setattr(account_service, "delete_identity", identity)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="private"))
    ) as client:
        provider.client = client
        with pytest.raises(HTTPException) as error:
            account_service.request_deletion(
                runtime_engine, reference.owner, lambda: Identity(id=reference.owner)
            )
    assert error.value.status_code == 503 and "private" not in error.value.detail
    identity.assert_not_called()
    with Session(admin_engine) as session:
        assert session.get(User, reference.owner).deletion_requested_at is not None
        assert (
            session.exec(select(Subscription).where(Subscription.user_id == reference.owner))
            .one()
            .external_id
            == "sub_demo"
        )
