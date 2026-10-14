import json
import os
import time
from re import fullmatch
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from app.account_routes import EngineDep, IdentityDep
from app.agent_routes import handled, no_store
from app.billing_access import BillingStatus, PortalResult, portal, status
from app.billing_database import billing_engine
from app.billing_events import process_event
from app.billing_resolution import EVENT_TYPES
from app.billing_service import CheckoutResult, checkout
from app.billing_signatures import stripe_signature
from app.billing_stripe import API_VERSION, BillingUnavailable, StripeSandbox

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


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request) -> dict[str, bool]:
    if os.environ.get("BILLING_ENABLED") != "true":
        raise HTTPException(503, "Cobrança de teste desativada.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 65536:
            raise HTTPException(413, "Evento excede o limite.")
        body.extend(chunk)
    if not stripe_signature(
        bytes(body),
        request.headers.get("Stripe-Signature", ""),
        os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        int(time.time()),
    ):
        raise HTTPException(400, "Assinatura de evento inválida.")
    try:
        event = json.loads(body)
        if (
            not isinstance(event, dict)
            or event.get("livemode") is not False
            or event.get("api_version") != API_VERSION
            or not isinstance(event.get("id"), str)
            or not fullmatch(r"evt_[A-Za-z0-9_]+", event["id"])
            or not isinstance(event.get("type"), str)
        ):
            raise ValueError
        if event["type"] not in EVENT_TYPES:
            return {"received": True}
        object_id = event["data"]["object"]["id"]
        if not isinstance(object_id, str):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Contrato de evento inválido.") from None

    def deliver() -> None:
        with httpx.Client(trust_env=False) as client:
            process_event(
                billing_engine(), provider_for(client), event["id"], event["type"], object_id
            )

    try:
        await run_in_threadpool(deliver)
    except BillingUnavailable:
        raise HTTPException(503, "Evento de teste temporariamente indisponível.") from None
    return {"received": True}
