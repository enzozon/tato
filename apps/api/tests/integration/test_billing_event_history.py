from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app import billing_events
from app.account_service import account_session
from app.billing_database import billing_account_session
from app.billing_stripe import StripeSandbox
from app.models import BillingCheckout, BillingEvent, Subscription, User
from tests.integration.test_billing_database_runtime import billing_runtime as billing_runtime
from tests.test_billing_payment import payment_chain as payment_chain

pytestmark = pytest.mark.integration


@pytest.fixture
def history(runtime_engine, owners, payment_chain):
    owner = owners[0]
    suffix = uuid4().hex
    customer = f"cus_{suffix}"
    requests = {name: uuid4() for name in ("old", "new")}
    deadlines = {"old": datetime(2026, 11, 1, tzinfo=UTC), "new": datetime(2026, 12, 1, tzinfo=UTC)}
    checkouts, subscriptions = {}, {}
    for name in requests:
        subscription_id = f"sub_{name}_{suffix}"
        checkout_id = f"cs_test_{name}_{suffix}"
        metadata = {"user_id": str(owner), "request_id": str(requests[name])}
        checkouts[name] = {
            "id": checkout_id,
            "livemode": False,
            "mode": "subscription",
            "currency": "brl",
            "amount_total": 3900,
            "client_reference_id": str(owner),
            "metadata": metadata,
            "status": "complete",
            "payment_status": "paid",
            "customer": customer,
            "subscription": subscription_id,
        }
        subscriptions[name] = {
            "id": subscription_id,
            "customer": customer,
            "livemode": False,
            "status": "active",
            "metadata": metadata,
            "latest_invoice": "in_demo",
            "items": {
                "has_more": False,
                "data": [
                    {
                        "quantity": 1,
                        "current_period_end": int(deadlines[name].timestamp()),
                        "price": {
                            "id": "price_test",
                            "livemode": False,
                            "currency": "brl",
                            "unit_amount": 3900,
                            "recurring": {"interval": "month", "interval_count": 1},
                        },
                    }
                ],
            },
        }
        with account_session(runtime_engine, owner) as session:
            session.add(
                BillingCheckout(
                    user_id=owner,
                    provider="stripe",
                    request_id=requests[name],
                    amount_cents=3900,
                    external_id=checkout_id,
                )
            )
    payment_chain["intent"]["customer"] = customer
    payment_chain["charge"]["customer"] = customer
    current = "old"
    calls = []

    def transport(request):
        nonlocal current
        calls.append(request.url.path)
        assert request.method == "GET"
        for name in requests:
            if request.url.path == f"/v1/checkout/sessions/{checkouts[name]['id']}":
                return httpx.Response(200, json=checkouts[name])
            if request.url.path == f"/v1/subscriptions/{subscriptions[name]['id']}":
                current = name
                return httpx.Response(200, json=subscriptions[name])
        if request.url.path == "/v1/invoices/in_demo":
            assert request.url.params["expand[]"] == "payments"
            return httpx.Response(
                200,
                json={
                    "id": "in_demo",
                    "customer": customer,
                    "livemode": False,
                    "currency": "brl",
                    "status": "paid",
                    "amount_paid": 3900,
                    "payments": payment_chain["invoice"]["payments"],
                    "parent": {
                        "type": "subscription_details",
                        "subscription_details": {
                            "subscription": subscriptions[current]["id"],
                        },
                    },
                },
            )
        for resource, key in (("payment_intents/pi_demo", "intent"), ("charges/ch_demo", "charge")):
            if request.url.path == f"/v1/{resource}":
                return httpx.Response(200, json=payment_chain[key])
        pytest.fail(f"Recurso sintético inesperado: {request.url.path}")

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox(
            "sk_test_synthetic", "price_test", client, "https://tato.example/app/"
        )
        yield provider, checkouts, subscriptions, deadlines, calls


def test_old_subscription_replay_preserves_new_plan_deadline_and_event_dedup(
    billing_runtime,
    owners,
    history,
):
    provider, checkouts, subscriptions, deadlines, calls = history
    owner = owners[0]
    assert billing_events.process_event(
        billing_runtime,
        provider,
        "evt_history_old",
        "checkout.session.completed",
        checkouts["old"]["id"],
    )
    with billing_account_session(billing_runtime, owner) as session:
        assert session.scalar(text("SELECT current_user")) == "tato_billing"
        previous = session.exec(select(Subscription)).one()
        assert previous.external_id == subscriptions["old"]["id"]
        assert previous.valid_until == deadlines["old"]
    subscriptions["old"]["status"] = "canceled"
    assert billing_events.process_event(
        billing_runtime,
        provider,
        "evt_history_new",
        "checkout.session.completed",
        checkouts["new"]["id"],
    )
    # Um ID novo para evento antigo é registrado, mas não troca a assinatura atual.
    for event_id in ("evt_history_late_old", "evt_history_late_old", "evt_history_old"):
        assert (
            billing_events.process_event(
                billing_runtime,
                provider,
                event_id,
                "checkout.session.completed",
                checkouts["old"]["id"],
            )
            is False
        )
        with billing_account_session(billing_runtime, owner) as session:
            current = session.exec(select(Subscription)).one()
            assert (current.external_id, current.plan, current.status, current.valid_until) == (
                subscriptions["new"]["id"],
                "pro",
                "active",
                deadlines["new"],
            )
            events = session.exec(select(BillingEvent)).all()
            assert {event.event_id for event in events} == {
                "evt_history_old",
                "evt_history_new",
                "evt_history_late_old",
            }
            assert len(events) == 3
            assert all(row.status == "paid" for row in session.exec(select(BillingCheckout)).all())
    assert f"/v1/subscriptions/{subscriptions['old']['id']}" in calls
    with billing_account_session(billing_runtime, owners[1]) as session:
        assert session.exec(select(Subscription)).all() == []
        assert session.exec(select(BillingEvent)).all() == []


def test_event_for_removed_user_does_not_recreate_account_or_billing_rows(
    billing_runtime,
    runtime_engine,
    admin_engine,
    owners,
    history,
):
    provider, checkouts, subscriptions, deadlines, calls = history
    owner = owners[0]
    assert billing_events.process_event(
        billing_runtime,
        provider,
        "evt_removed_before",
        "checkout.session.completed",
        checkouts["old"]["id"],
    )
    with account_session(runtime_engine, owner) as session:
        session.delete(session.get(User, owner))
    calls.clear()
    assert (
        billing_events.process_event(
            billing_runtime,
            provider,
            "evt_removed_after",
            "checkout.session.completed",
            checkouts["old"]["id"],
        )
        is False
    )
    assert calls == [f"/v1/checkout/sessions/{checkouts['old']['id']}"]
    with Session(admin_engine) as session:
        assert session.get(User, owner) is None
        assert session.get(User, owners[1]) is not None
        for model in (Subscription, BillingCheckout, BillingEvent):
            assert session.exec(select(model).where(model.user_id == owner)).all() == []
