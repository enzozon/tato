from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.billing_access import status
from app.billing_service import checkout
from app.billing_stripe import BillingUnavailable, StripeCheckout
from app.models import BillingCheckout, Subscription

pytestmark = pytest.mark.integration


@pytest.fixture
def canceled(admin_engine, owners, monkeypatch):
    owner, _ = owners
    original = uuid4()
    monkeypatch.setattr("app.billing_service.check_rate", lambda *args: None)
    monkeypatch.setattr("app.billing_access.check_rate", lambda *args: None)
    with Session(admin_engine) as session, session.begin():
        session.add(
            Subscription(
                user_id=owner,
                plan="pro",
                status="canceled",
                billing_provider="stripe",
                external_id="sub_old",
                external_customer_id="cus_owner",
                valid_until=datetime.now(UTC) + timedelta(days=30),
            )
        )
        session.add(
            BillingCheckout(
                user_id=owner,
                provider="stripe",
                request_id=original,
                amount_cents=3900,
                status="paid",
                external_id="cs_test_old",
            )
        )
    provider = Mock()
    provider.request.return_value = {
        "id": "sub_old",
        "livemode": False,
        "customer": "cus_owner",
        "metadata": {"user_id": str(owner)},
        "status": "canceled",
    }
    return owner, original, provider


def test_canceled_repurchase_reuses_customer_and_old_uuid_stays_idempotent(
    runtime_engine,
    admin_engine,
    canceled,
):
    owner, original, provider = canceled
    assert status(runtime_engine, owner, True).can_checkout
    assert checkout(runtime_engine, owner, original, provider).status == "paid"
    provider.checkout.assert_not_called()
    request_id = uuid4()
    remote = StripeCheckout(
        id="cs_test_new",
        livemode=False,
        mode="subscription",
        currency="brl",
        amount_total=3900,
        client_reference_id=str(owner),
        metadata={"user_id": str(owner), "request_id": str(request_id)},
        status="open",
        payment_status="unpaid",
        customer="cus_owner",
        url="https://checkout.stripe.com/c/pay/new",
    )
    provider.checkout.return_value = remote
    first = checkout(runtime_engine, owner, request_id, provider)
    provider.checkout.assert_called_once_with(owner, request_id, "cus_owner")
    provider.retrieve_checkout.return_value = remote
    assert checkout(runtime_engine, owner, request_id, provider) == first
    assert provider.checkout.call_count == 1
    with Session(admin_engine) as session:
        existing = session.exec(select(Subscription).where(Subscription.user_id == owner)).one()
        assert existing.external_id == "sub_old" and existing.status == "canceled"
        assert existing.external_customer_id == "cus_owner"
    with pytest.raises(HTTPException):
        checkout(runtime_engine, owner, uuid4(), provider)


@pytest.mark.parametrize("remote_status", ["active", "past_due", "unpaid", "paused"])
def test_remote_nonterminal_blocks_repurchase_without_reserving(
    runtime_engine,
    admin_engine,
    canceled,
    remote_status,
):
    owner, _, provider = canceled
    provider.request.return_value["status"] = remote_status
    with pytest.raises(HTTPException) as error:
        checkout(runtime_engine, owner, uuid4(), provider)
    assert error.value.status_code == 409
    provider.checkout.assert_not_called()
    with Session(admin_engine) as session:
        rows = session.exec(select(BillingCheckout).where(BillingCheckout.user_id == owner)).all()
        assert len(rows) == 1


@pytest.mark.parametrize("field,value", [("customer", "cus_other"), ("metadata", {})])
def test_remote_mismatched_binding_blocks_repurchase(runtime_engine, canceled, field, value):
    owner, _, provider = canceled
    provider.request.return_value[field] = value
    with pytest.raises(BillingUnavailable):
        checkout(runtime_engine, owner, uuid4(), provider)
    provider.checkout.assert_not_called()
