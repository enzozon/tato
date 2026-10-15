from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlmodel import select

from app import billing_events
from app.account_service import account_session
from app.billing_database import billing_account_session
from app.billing_resolution import SubscriptionReference
from app.billing_stripe import BillingUnavailable, StripeCheckout, StripeSubscriptionState
from app.models import BillingCheckout, BillingEvent, Subscription, User
from tests.integration.test_billing_database_runtime import billing_runtime as billing_runtime

pytestmark = pytest.mark.integration


@pytest.fixture
def processor(runtime_engine, owners, monkeypatch):
    owner, other = owners
    request_id = uuid4()
    reference = SubscriptionReference(owner, request_id, "sub_demo", "cus_demo")
    monkeypatch.setattr(billing_events, "resolve_subscription", lambda *args: reference)
    with account_session(runtime_engine, owner) as session:
        session.add(
            BillingCheckout(
                user_id=owner,
                provider="stripe",
                request_id=request_id,
                amount_cents=3900,
                external_id="cs_test_demo",
            )
        )
    provider = Mock()
    provider.retrieve_checkout.return_value = StripeCheckout(
        id="cs_test_demo",
        livemode=False,
        mode="subscription",
        currency="brl",
        amount_total=3900,
        client_reference_id=str(owner),
        metadata={"user_id": str(owner), "request_id": str(request_id)},
        status="complete",
        payment_status="paid",
        customer="cus_demo",
        subscription="sub_demo",
    )
    provider.subscription_state.return_value = StripeSubscriptionState(
        id="sub_demo",
        customer="cus_demo",
        status="active",
        valid_until=datetime(2026, 11, 1, tzinfo=UTC),
    )
    return provider, reference


def test_persistent_replay_concurrency_and_tenant_isolation(billing_runtime, owners, processor):
    provider, reference = processor

    def run(index):
        return billing_events.process_event(
            billing_runtime, provider, "evt_shared", "invoice.paid", "in_demo"
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(run, range(2))) == [False, True]
    with billing_account_session(billing_runtime, owners[0]) as session:
        assert len(session.exec(select(BillingEvent)).all()) == 1
        assert session.exec(select(Subscription)).one().status == "active"
    with billing_account_session(billing_runtime, owners[1]) as session:
        assert session.exec(select(Subscription)).all() == []
        assert session.exec(select(BillingEvent)).all() == []


def test_remote_failure_rolls_back_and_old_snapshot_recalculates_current_state(
    billing_runtime, processor
):
    provider, reference = processor
    provider.subscription_state.side_effect = BillingUnavailable("synthetic")
    with pytest.raises(BillingUnavailable):
        billing_events.process_event(
            billing_runtime, provider, "evt_retry", "invoice.paid", "in_demo"
        )
    with billing_account_session(billing_runtime, reference.owner) as session:
        assert session.exec(select(BillingEvent)).all() == []
        assert session.exec(select(Subscription)).all() == []
        assert session.exec(select(BillingCheckout)).one().status == "pending"
    provider.subscription_state.side_effect = None
    provider.subscription_state.return_value.status = "past_due"
    assert billing_events.process_event(
        billing_runtime, provider, "evt_retry", "invoice.paid", "in_demo"
    )
    with billing_account_session(billing_runtime, reference.owner) as session:
        assert session.exec(select(Subscription)).one().status == "past_due"
    # Um evento antigo de expiração não aplica seu snapshot: consulta pagamento corrente.
    provider.subscription_state.return_value.status = "active"
    assert billing_events.process_event(
        billing_runtime, provider, "evt_old", "checkout.session.expired", "cs_test_demo"
    )
    with billing_account_session(billing_runtime, reference.owner) as session:
        assert session.exec(select(Subscription)).one().status == "active"


def test_deletion_pending_and_cross_customer_binding_do_not_apply(
    billing_runtime, runtime_engine, processor
):
    provider, reference = processor
    provider.retrieve_checkout.return_value.customer = "cus_other"
    with pytest.raises(BillingUnavailable):
        billing_events.process_event(
            billing_runtime, provider, "evt_wrong", "invoice.paid", "in_demo"
        )
    with billing_account_session(billing_runtime, reference.owner) as session:
        assert session.exec(select(BillingEvent)).all() == []
    provider.retrieve_checkout.return_value.customer = "cus_demo"
    with account_session(runtime_engine, reference.owner) as session:
        user = session.get(User, reference.owner)
        user.deletion_requested_at = datetime.now(UTC)
        session.add(user)
    assert (
        billing_events.process_event(
            billing_runtime, provider, "evt_delete", "invoice.paid", "in_demo"
        )
        is False
    )
    provider.subscription_state.assert_not_called()


def test_persisted_customer_binding_cannot_be_overwritten(billing_runtime, processor):
    provider, reference = processor
    with billing_account_session(billing_runtime, reference.owner) as session:
        session.add(
            Subscription(
                user_id=reference.owner,
                billing_provider="stripe",
                external_id="sub_demo",
                external_customer_id="cus_other",
                status="canceled",
            )
        )
    with pytest.raises(BillingUnavailable):
        billing_events.process_event(
            billing_runtime, provider, "evt_rebind", "invoice.paid", "in_demo"
        )
    with billing_account_session(billing_runtime, reference.owner) as session:
        assert session.exec(select(Subscription)).one().external_customer_id == "cus_other"
        assert session.exec(select(BillingEvent)).all() == []
