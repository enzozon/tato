from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlmodel import select

from app.account_service import account_session
from app.billing_stripe import StripeSandbox, hosted_url
from app.llm_service import require_active
from app.models import BillingCheckout, Subscription
from app.plans import user_plan
from app.rate_limit import check_rate


class CheckoutResult(BaseModel):
    request_id: UUID
    status: Literal["pending", "paid", "canceled"]
    checkout_url: str | None = None


def checkout(
    engine: Engine, owner: UUID, request_id: UUID, provider: StripeSandbox
) -> CheckoutResult:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        plan = user_plan(session, owner)
        check_rate(owner, plan.requests_per_minute)
        row = session.exec(
            select(BillingCheckout).where(
                BillingCheckout.user_id == owner, BillingCheckout.request_id == request_id
            )
        ).first()
        if row is None:
            subscription = session.exec(
                select(Subscription).where(Subscription.user_id == owner)
            ).first()
            if plan.name == "pro" or (subscription and subscription.billing_provider is not None):
                raise HTTPException(409, "Gerencie a assinatura existente antes de criar outra.")
            pending = session.exec(
                select(BillingCheckout).where(
                    BillingCheckout.user_id == owner, BillingCheckout.status == "pending"
                )
            ).first()
            if pending is not None:
                raise HTTPException(409, "Já existe checkout pendente; repita o pedido original.")
            session.add(
                BillingCheckout(
                    user_id=owner, request_id=request_id, provider="stripe", amount_cents=3900
                )
            )
        elif row.provider != "stripe":
            raise HTTPException(409, "Pedido vinculado a outro provedor.")
    # Reserva confirmada antes do efeito remoto; o mesmo UUID reutiliza a chave Stripe.
    with account_session(engine, owner) as session:
        require_active(session, owner)
        row = session.exec(
            select(BillingCheckout).where(
                BillingCheckout.user_id == owner, BillingCheckout.request_id == request_id
            )
        ).one()
        if row.status != "pending":
            return CheckoutResult.model_validate({"request_id": request_id, "status": row.status})
        if row.external_id is None:
            if datetime.now(UTC) - row.created_at >= timedelta(hours=23):
                raise HTTPException(
                    409, "Pedido sem vínculo expirado; exige reconciliação operacional."
                )
            remote = provider.checkout(owner, request_id)
            row.external_id = remote.id
        else:
            remote = provider.retrieve_checkout(row.external_id, owner, request_id)
        url = hosted_url(remote.url) if remote.status == "open" else None
        if remote.status == "expired":
            row.status = "canceled"
            row.completed_at = datetime.now(UTC)
        session.add(row)
        return CheckoutResult.model_validate(
            {"request_id": request_id, "status": row.status, "checkout_url": url}
        )
