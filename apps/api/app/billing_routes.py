import os
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.account_routes import EngineDep, IdentityDep
from app.agent_routes import handled, no_store
from app.billing_service import CheckoutResult, checkout
from app.billing_stripe import BillingUnavailable, StripeSandbox

router = APIRouter(prefix="/billing", tags=["cobrança de teste"], dependencies=[Depends(no_store)])


class CheckoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


@router.post("/stripe/checkout", response_model=CheckoutResult)
def stripe_checkout(
    data: CheckoutInput, identity: IdentityDep, engine: EngineDep
) -> CheckoutResult:
    if os.environ.get("BILLING_ENABLED") != "true":
        raise HTTPException(503, "Cobrança de teste desativada.")
    try:
        with httpx.Client(trust_env=False) as client:
            provider = StripeSandbox(
                os.environ.get("STRIPE_SECRET_KEY", ""),
                os.environ.get("STRIPE_PRICE_ID", ""),
                client,
                os.environ.get("BILLING_RETURN_URL", ""),
            )
            with handled():
                return checkout(engine, identity.id, data.request_id, provider)
    except BillingUnavailable:
        raise HTTPException(503, "Cobrança de teste temporariamente indisponível.") from None
