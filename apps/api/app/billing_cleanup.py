from re import fullmatch
from typing import Any
from uuid import UUID

import httpx
from sqlmodel import Session, select

from app.billing_resolution import find_reserved_checkout
from app.billing_stripe import API_VERSION, BillingUnavailable, StripeCheckout, StripeSandbox
from app.models import BillingCheckout, Subscription


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


def cleanup(session: Session, owner: UUID, provider: StripeSandbox) -> None:
    """Executado sob account_session, após confirmar o marcador de exclusão."""
    subscription = session.exec(select(Subscription).where(Subscription.user_id == owner)).first()
    rows = session.exec(select(BillingCheckout).where(BillingCheckout.user_id == owner)).all()
    if subscription is not None and subscription.billing_provider not in {None, "stripe"}:
        raise BillingUnavailable("Provedor de limpeza indisponível.")
    customers: set[str] = set()
    bindings: set[tuple[str, str | None]] = set()
    for row in rows:
        if row.provider != "stripe":
            raise BillingUnavailable("Provedor de limpeza indisponível.")
        if row.external_id is None:
            remote = find_reserved_checkout(provider, owner, row.request_id, row.created_at)
            if remote is None:
                # Ausência na listagem não prova ausência de efeito remoto em reserva pendente.
                raise BillingUnavailable("Reserva de checkout exige reconciliação.")
            remote = provider.retrieve_checkout(remote.id, owner, row.request_id)
        else:
            remote = provider.retrieve_checkout(row.external_id, owner, row.request_id)
        if remote.status == "open":
            remote = expire_checkout(provider, remote, owner, row.request_id)
        if remote.status == "complete":
            if remote.customer is None:
                raise BillingUnavailable("Cliente do checkout ainda indisponível.")
            bindings.add((remote.customer, remote.subscription))
        if remote.customer is not None:
            customers.add(remote.customer)
    if (
        subscription is not None
        and subscription.billing_provider == "stripe"
        and (
            subscription.external_customer_id is None
            or subscription.external_id is None
            or (subscription.external_customer_id, subscription.external_id) not in bindings
        )
    ):
        raise BillingUnavailable("Vínculo de assinatura exige reconciliação.")
    # Todas as referências foram verificadas antes de remover qualquer cliente.
    for customer_id in sorted(customers):
        if not customer_request(provider, "GET", customer_id):
            customer_request(provider, "DELETE", customer_id)
