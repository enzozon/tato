from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlmodel import Session

from app.billing_access import portal, status
from app.billing_stripe import BillingUnavailable
from app.llm import LLMUnavailable
from app.models import BillingCheckout, Subscription, User

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_remote_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr("app.billing_access.check_rate", lambda *args: None)


@pytest.mark.parametrize("enabled", [False, True])
def test_status_free_is_private_and_respects_disabled_flag(
    admin_engine: Engine, runtime_engine: Engine, owners: tuple[UUID, UUID], enabled: bool
) -> None:
    owner, other = owners
    with Session(admin_engine) as session, session.begin():
        session.add(
            Subscription(
                user_id=other,
                plan="pro",
                billing_provider="stripe",
                external_id="sub_other",
                external_customer_id="cus_other",
                valid_until=datetime.now(UTC) + timedelta(days=30),
            )
        )
        session.add(
            BillingCheckout(user_id=other, provider="stripe", request_id=uuid4(), amount_cents=3900)
        )
    result = status(runtime_engine, owner, enabled)
    assert result.enabled is enabled
    assert result.mode == "test"
    assert result.can_checkout is enabled
    assert result.can_portal is False
    assert result.pending_request_id is None
    assert "cus_other" not in result.model_dump_json()


@pytest.mark.parametrize("provider", ["stripe", "abacatepay"])
@pytest.mark.parametrize("enabled", [False, True])
def test_status_pending_checkout_can_only_resume_owned_stripe(
    admin_engine: Engine,
    runtime_engine: Engine,
    owners: tuple[UUID, UUID],
    provider: str,
    enabled: bool,
) -> None:
    owner, _ = owners
    request_id = uuid4()
    with Session(admin_engine) as session, session.begin():
        session.add(
            BillingCheckout(
                user_id=owner, provider=provider, request_id=request_id, amount_cents=3900
            )
        )
    result = status(runtime_engine, owner, enabled)
    assert result.can_checkout is (enabled and provider == "stripe")
    assert result.can_portal is False
    assert result.pending_request_id == (request_id if provider == "stripe" else None)


@pytest.mark.parametrize(
    ("plan", "provider", "customer", "can_portal"),
    [
        ("pro", None, None, False),
        ("pro", "stripe", "cus_owner", True),
        ("free", "stripe", "cus_owner", True),
        ("free", "stripe", "invalid", False),
        ("free", "abacatepay", "cus_owner", False),
    ],
)
def test_status_subscription_blocks_new_purchase_and_only_stripe_offers_portal(
    admin_engine: Engine,
    runtime_engine: Engine,
    owners: tuple[UUID, UUID],
    plan: str,
    provider: str | None,
    customer: str | None,
    can_portal: bool,
) -> None:
    owner, _ = owners
    with Session(admin_engine) as session, session.begin():
        session.add(
            Subscription(
                user_id=owner,
                plan=plan,
                billing_provider=provider,
                external_id="sub_owner" if provider else None,
                external_customer_id=customer,
                valid_until=datetime.now(UTC) + timedelta(days=30) if provider else None,
            )
        )
    result = status(runtime_engine, owner, True)
    assert result.can_checkout is False
    assert result.can_portal is can_portal
    disabled = status(runtime_engine, owner, False)
    assert disabled.can_checkout is False and disabled.can_portal is False


def test_portal_uses_only_owned_subscription_customer(
    admin_engine: Engine, runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    owner, other = owners
    with Session(admin_engine) as session, session.begin():
        session.add(
            Subscription(
                user_id=owner,
                billing_provider="stripe",
                external_id="sub_owner",
                external_customer_id="cus_owner",
            )
        )
    provider = Mock()
    provider.portal.return_value = "https://billing.stripe.com/p/session/demo"
    request_id = uuid4()
    result = portal(runtime_engine, owner, request_id, provider)
    assert result.portal_url == provider.portal.return_value
    provider.portal.assert_called_once_with("cus_owner", request_id)
    provider.reset_mock()
    with pytest.raises(HTTPException) as error:
        portal(runtime_engine, other, request_id, provider)
    assert error.value.status_code == 409
    provider.portal.assert_not_called()


def test_deletion_pending_blocks_status_and_portal_before_network(
    admin_engine: Engine, runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    owner, _ = owners
    with Session(admin_engine) as session, session.begin():
        user = session.get(User, owner)
        assert user is not None
        user.deletion_requested_at = datetime.now(UTC)
        session.add(user)
    with pytest.raises(LLMUnavailable):
        status(runtime_engine, owner, True)
    provider = Mock()
    with pytest.raises(LLMUnavailable):
        portal(runtime_engine, owner, uuid4(), provider)
    provider.portal.assert_not_called()


def test_invalid_local_customer_cannot_reach_provider(
    admin_engine: Engine, runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    owner, _ = owners
    with Session(admin_engine) as session, session.begin():
        session.add(
            Subscription(
                user_id=owner,
                billing_provider="stripe",
                external_id="sub_owner",
                external_customer_id="cus_owner/path",
            )
        )
    provider = Mock()
    with pytest.raises(BillingUnavailable):
        portal(runtime_engine, owner, uuid4(), provider)
    provider.portal.assert_not_called()
