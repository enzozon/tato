from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import billing_events
from app.billing_stripe import BillingUnavailable, StripeCheckout, StripeSubscriptionState
from app.models import BillingCheckout, Subscription


@pytest.mark.parametrize(
    "remote_status,state_status",
    [
        ("expired", "canceled"),
        ("open", "past_due"),
        ("complete", "active"),
        ("complete", "past_due"),
    ],
)
def test_apply_uses_current_verified_state_without_claiming_snapshot_payment(
    remote_status, state_status
):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        amount_cents=3900,
        external_id="cs_test_demo",
    )
    remote = StripeCheckout(
        id="cs_test_demo",
        livemode=False,
        mode="subscription",
        currency="brl",
        amount_total=3900,
        client_reference_id=str(owner),
        metadata={"user_id": str(owner), "request_id": str(request_id)},
        status=remote_status,
        payment_status="paid" if remote_status == "complete" else "unpaid",
        customer="cus_demo",
        subscription="sub_demo",
    )
    provider, session = Mock(), Mock()
    provider.retrieve_checkout.return_value = remote
    provider.subscription_state.return_value = StripeSubscriptionState(
        id="sub_demo",
        customer="cus_demo",
        status=state_status,
        valid_until=datetime(2026, 11, 1, tzinfo=UTC),
    )
    session.exec.return_value.first.return_value = None
    assert billing_events.apply_checkout(session, provider, row)
    if remote_status == "complete":
        subscription = session.add.call_args_list[0].args[0]
        assert subscription.status == state_status
        assert row.status == "paid"
    else:
        provider.subscription_state.assert_not_called()
        assert row.status == ("canceled" if remote_status == "expired" else "pending")


def test_old_event_cannot_overwrite_new_subscription_and_mismatch_fails():
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        amount_cents=3900,
        external_id="cs_test_old",
        status="paid",
    )
    remote = SimpleNamespace(
        id="cs_test_old",
        subscription="sub_old",
        customer="cus_demo",
        status="complete",
        payment_status="paid",
    )
    provider, session = Mock(), Mock()
    provider.retrieve_checkout.return_value = remote
    session.exec.return_value.first.return_value = Subscription(
        user_id=owner,
        billing_provider="stripe",
        external_id="sub_new",
        external_customer_id="cus_demo",
    )
    assert billing_events.apply_checkout(session, provider, row) is False
    provider.subscription_state.assert_not_called()
    reference = billing_events.SubscriptionReference(owner, request_id, "sub_other", "cus_demo")
    with pytest.raises(BillingUnavailable):
        billing_events.apply_checkout(session, provider, row, reference)


def test_missing_remote_checkout_never_recreates_it(monkeypatch):
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner, provider="stripe", request_id=request_id, amount_cents=3900
    )
    monkeypatch.setattr(billing_events, "find_reserved_checkout", lambda *args: None)
    provider = Mock()
    with pytest.raises(BillingUnavailable):
        billing_events.apply_checkout(Mock(), provider, row)
    provider.checkout.assert_not_called()


def test_expired_repurchase_cancels_only_reservation_and_preserves_old_subscription():
    owner, request_id = uuid4(), uuid4()
    row = BillingCheckout(
        user_id=owner,
        provider="stripe",
        request_id=request_id,
        amount_cents=3900,
        external_id="cs_test_new",
    )
    current = Subscription(
        user_id=owner, billing_provider="stripe", external_id="sub_old", status="canceled"
    )
    provider, session = Mock(), Mock()
    provider.retrieve_checkout.return_value = SimpleNamespace(
        id="cs_test_new", subscription=None, customer=None, status="expired"
    )
    session.exec.return_value.first.return_value = current
    assert billing_events.apply_checkout(session, provider, row)
    assert row.status == "canceled" and row.completed_at is not None
    assert current.external_id == "sub_old" and current.status == "canceled"
    assert session.add.call_args.args[0] is row
    provider.subscription_state.assert_not_called()
