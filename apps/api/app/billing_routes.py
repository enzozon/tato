import os
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.account_routes import EngineDep, IdentityDep
from app.agent_routes import handled, no_store
from app.billing_access import BillingStatus, PortalResult, portal, status
from app.billing_service import CheckoutResult, checkout
from app.billing_stripe import BillingUnavailable, StripeSandbox

router = APIRouter(prefix="/billing", tags=["cobrança de teste"], dependencies=[Depends(no_store)])


class CheckoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


def provider_for(client: httpx.Client) -> StripeSandbox:
    return StripeSandbox(
        os.environ.get("STRIPE_SECRET_KEY", ""),
        os.environ.get("STRIPE_PRICE_ID", ""),
        client,
        os.environ.get("BILLING_RETURN_URL", ""),
    )


@router.get("/status", response_model=BillingStatus)
def billing_status(identity: IdentityDep, engine: EngineDep) -> BillingStatus:
    enabled = os.environ.get("BILLING_ENABLED") == "true"
    if enabled:
        try:
            with httpx.Client(trust_env=False) as client:
                provider_for(client)
        except BillingUnavailable:
            enabled = False
    with handled():
        return status(engine, identity.id, enabled)


@router.post("/stripe/portal", response_model=PortalResult)
def stripe_portal(data: CheckoutInput, identity: IdentityDep, engine: EngineDep) -> PortalResult:
    if os.environ.get("BILLING_ENABLED") != "true":
        raise HTTPException(503, "Cobrança de teste desativada.")
    try:
        with httpx.Client(trust_env=False) as client, handled():
            return portal(engine, identity.id, data.request_id, provider_for(client))
    except BillingUnavailable:
        raise HTTPException(503, "Cobrança de teste temporariamente indisponível.") from None


@router.post("/stripe/checkout", response_model=CheckoutResult)
def stripe_checkout(
    data: CheckoutInput, identity: IdentityDep, engine: EngineDep
) -> CheckoutResult:
    if os.environ.get("BILLING_ENABLED") != "true":
        raise HTTPException(503, "Cobrança de teste desativada.")
    try:
        with httpx.Client(trust_env=False) as client:
            provider = provider_for(client)
            with handled():
                return checkout(engine, identity.id, data.request_id, provider)
    except BillingUnavailable:
        raise HTTPException(503, "Cobrança de teste temporariamente indisponível.") from None
