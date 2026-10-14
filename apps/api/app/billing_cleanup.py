from re import fullmatch
from typing import Any
from uuid import UUID

import httpx

from app.billing_stripe import API_VERSION, BillingUnavailable, StripeCheckout, StripeSandbox


def customer_request(provider: StripeSandbox, method: str, customer_id: str) -> bool:
    """Tombstone não tem livemode; aceite apenas o ID esperado sob chave de teste."""
    if (
        not provider.key.startswith("sk_test_")
        or not fullmatch(r"cus_[A-Za-z0-9_]+", customer_id)
        or method not in {"GET", "DELETE"}
    ):
        raise BillingUnavailable("Referência de cliente de teste inválida.")
    try:
        response = provider.client.request(
            method,
            f"https://api.stripe.com/v1/customers/{customer_id}",
            headers={"Authorization": f"Bearer {provider.key}", "Stripe-Version": API_VERSION},
            timeout=10,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload: Any = response.json()
        if (
            not isinstance(payload, dict)
            or payload.get("id") != customer_id
            or payload.get("object") != "customer"
        ):
            raise BillingUnavailable("Vínculo de cliente de teste inválido.")
        if payload.get("deleted") is True:
            if "livemode" in payload and payload["livemode"] is not False:
                raise BillingUnavailable("Cliente fora do modo de teste.")
            return True
        if method == "DELETE" or payload.get("livemode") is not False or "deleted" in payload:
            raise BillingUnavailable("Estado de cliente de teste inválido.")
        return False
    except (httpx.HTTPError, ValueError):
        raise BillingUnavailable("Limpeza Stripe de teste indisponível.") from None


def expire_checkout(
    provider: StripeSandbox, remote: StripeCheckout, owner: UUID, request_id: UUID
) -> StripeCheckout:
    try:
        payload = provider.request("POST", f"checkout/sessions/{remote.id}/expire")
    except BillingUnavailable:
        # Um pagamento pode terminar entre GET e expire; releia sem criar outra sessão.
        result = provider.retrieve_checkout(remote.id, owner, request_id)
        if result.status == "open":
            raise BillingUnavailable("Checkout de teste ainda aberto.") from None
        return result
    result = provider.validate_checkout(payload, owner, request_id)
    if result.id != remote.id or result.status != "expired":
        raise BillingUnavailable("Expiração de checkout inválida.")
    return result
