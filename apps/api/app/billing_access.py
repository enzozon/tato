from re import fullmatch
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import col, select

from app.account_service import account_session
from app.billing_stripe import BillingUnavailable, StripeSandbox
from app.llm_service import require_active
from app.models import BillingCheckout, Subscription
from app.plans import user_plan
from app.rate_limit import check_rate


class BillingStatus(BaseModel):
    enabled: bool
    mode: Literal["test"] = "test"
    can_checkout: bool
    can_portal: bool
    pending_request_id: UUID | None = None


class PortalResult(BaseModel):
    portal_url: str = Field(repr=False)


def status(engine: Engine, owner: UUID, enabled: bool) -> BillingStatus:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        plan = user_plan(session, owner)
        check_rate(owner, plan.requests_per_minute)
        subscription = session.exec(
            select(Subscription).where(Subscription.user_id == owner)
        ).first()
        pending = session.exec(
            select(BillingCheckout)
            .where(BillingCheckout.user_id == owner, BillingCheckout.status == "pending")
            .order_by(col(BillingCheckout.created_at), col(BillingCheckout.id))
        ).first()
        customer = subscription.external_customer_id if subscription else None
        linked = subscription is not None and subscription.billing_provider is not None
        return BillingStatus(
            enabled=enabled,
            can_checkout=enabled
            and plan.name != "pro"
            and not linked
            and (pending is None or pending.provider == "stripe"),
            can_portal=enabled
            and subscription is not None
            and subscription.billing_provider == "stripe"
            and isinstance(customer, str)
            and fullmatch(r"cus_[A-Za-z0-9_]+", customer) is not None,
            pending_request_id=pending.request_id
            if pending is not None and pending.provider == "stripe"
            else None,
        )


def portal(engine: Engine, owner: UUID, request_id: UUID, provider: StripeSandbox) -> PortalResult:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        subscription = session.exec(
            select(Subscription).where(Subscription.user_id == owner)
        ).first()
        if subscription is None or subscription.billing_provider != "stripe":
            raise HTTPException(409, "Não há assinatura Stripe de teste para gerenciar.")
        customer = subscription.external_customer_id
        if not isinstance(customer, str) or not fullmatch(r"cus_[A-Za-z0-9_]+", customer):
            raise BillingUnavailable("Vínculo de cliente de teste inválido.")
        # O lock mantém o vínculo estável enquanto a sessão temporária é criada.
        return PortalResult(portal_url=provider.portal(customer, request_id))
