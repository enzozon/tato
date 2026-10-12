from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlmodel import select

from app.account_service import account_session
from app.billing_service import checkout
from app.billing_stripe import BillingUnavailable, StripeCheckout
from app.llm import LLMUnavailable
from app.models import BillingCheckout, User
from app.plans import user_plan

pytestmark = pytest.mark.integration


def test_reservation_survives_remote_failure_and_reuses_known_checkout(
    runtime_engine: Engine, owners: tuple[UUID, UUID], monkeypatch
) -> None:
    monkeypatch.setattr("app.billing_service.check_rate", lambda *args: None)
    owner, other = owners
    request_id = uuid4()
    provider = Mock()
    provider.checkout.side_effect = BillingUnavailable("sintetico")
    with pytest.raises(BillingUnavailable):
        checkout(runtime_engine, owner, request_id, provider)
    with account_session(runtime_engine, owner) as session:
        row = session.exec(select(BillingCheckout)).one()
        assert row.external_id is None and row.request_id == request_id
    with pytest.raises(HTTPException) as error:
        checkout(runtime_engine, owner, uuid4(), provider)
    assert error.value.status_code == 409
    remote = StripeCheckout(
        id="cs_test_demo",
        livemode=False,
        mode="subscription",
        currency="brl",
        amount_total=3900,
        client_reference_id=str(owner),
        metadata={"user_id": str(owner), "request_id": str(request_id)},
        status="open",
        payment_status="unpaid",
        url="https://checkout.stripe.com/c/pay/demo",
    )
    provider.checkout.side_effect = None
    provider.checkout.return_value = remote
    first = checkout(runtime_engine, owner, request_id, provider)
    provider.retrieve_checkout.return_value = remote
    assert checkout(runtime_engine, owner, request_id, provider) == first
    assert provider.checkout.call_count == 2
    provider.retrieve_checkout.assert_called_once_with("cs_test_demo", owner, request_id)
    with account_session(runtime_engine, other) as session:
        assert session.exec(select(BillingCheckout)).all() == []
    with account_session(runtime_engine, owner) as session:
        assert user_plan(session, owner).name == "free"
        user = session.get(User, owner)
        user.deletion_requested_at = datetime.now(UTC)
        session.add(user)
    with pytest.raises(LLMUnavailable):
        checkout(runtime_engine, owner, request_id, provider)
    assert provider.retrieve_checkout.call_count == 1


def test_unknown_old_checkout_does_not_repeat_remote_creation(
    runtime_engine: Engine, owners: tuple[UUID, UUID], monkeypatch
) -> None:
    monkeypatch.setattr("app.billing_service.check_rate", lambda *args: None)
    owner, _ = owners
    request_id = uuid4()
    with account_session(runtime_engine, owner) as session:
        session.add(
            BillingCheckout(
                user_id=owner,
                request_id=request_id,
                provider="stripe",
                amount_cents=3900,
                created_at=datetime.now(UTC) - timedelta(hours=24),
            )
        )
    provider = Mock()
    with pytest.raises(HTTPException):
        checkout(runtime_engine, owner, request_id, provider)
    provider.checkout.assert_not_called()
