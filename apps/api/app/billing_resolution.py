"""Resolução de IDs remotos; nenhum payload é persistido ou registrado."""

from dataclasses import dataclass
from re import fullmatch
from typing import Any
from uuid import UUID

from app.billing_stripe import BillingUnavailable, StripeSandbox

EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.expired",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid",
        "invoice.payment_failed",
        "invoice.voided",
        "charge.refunded",
        "charge.dispute.created",
        "charge.dispute.updated",
        "charge.dispute.closed",
    }
)


@dataclass(frozen=True)
class SubscriptionReference:
    owner: UUID
    request_id: UUID
    subscription_id: str | None
    customer_id: str | None
    checkout_id: str | None = None


def object_by_id(provider: StripeSandbox, resource: str, value: Any, prefix: str) -> dict[str, Any]:
    if not isinstance(value, str) or not fullmatch(prefix + r"_[A-Za-z0-9_]+", value):
        raise BillingUnavailable("Referência Stripe inválida.")
    result = provider.request("GET", f"{resource}/{value}")
    if result.get("id") != value:
        raise BillingUnavailable("Referência Stripe divergente.")
    return result


def metadata_identity(payload: dict[str, Any]) -> tuple[UUID, UUID]:
    owner, request_id = payload["metadata"]["user_id"], payload["metadata"]["request_id"]
    if not isinstance(owner, str) or not isinstance(request_id, str):
        raise ValueError
    return UUID(owner), UUID(request_id)


def resolve_subscription(
    provider: StripeSandbox, kind: str, object_id: str
) -> SubscriptionReference:
    try:
        if kind not in EVENT_TYPES:
            raise ValueError
        value = object_id
        expected_customer = None
        if kind.startswith("charge.dispute."):
            value = object_by_id(provider, "disputes", value, "dp")["charge"]
        if kind.startswith("charge."):
            charge = object_by_id(provider, "charges", value, "ch")
            intent = object_by_id(provider, "payment_intents", charge["payment_intent"], "pi")
            if charge["customer"] != intent["customer"]:
                raise ValueError
            matches = provider.request(
                "GET",
                "invoice_payments",
                list_response=True,
                params={
                    "payment[type]": "payment_intent",
                    "payment[payment_intent]": intent["id"],
                    "limit": "100",
                },
            )
            rows = matches["data"]
            if matches["has_more"] or len(rows) != 1:
                raise ValueError
            payment = rows[0]
            if (
                payment["payment"]["type"] != "payment_intent"
                or payment["payment"]["payment_intent"] != intent["id"]
            ):
                raise ValueError
            invoice = object_by_id(provider, "invoices", payment["invoice"], "in")
            if invoice["customer"] != intent["customer"]:
                raise ValueError
            if invoice["parent"]["type"] != "subscription_details":
                raise ValueError
            expected_customer = invoice["customer"]
            value = invoice["parent"]["subscription_details"]["subscription"]
        elif kind.startswith("checkout."):
            checkout = object_by_id(provider, "checkout/sessions", value, "cs_test")
            owner, request_id = metadata_identity(checkout)
            validated = provider.validate_checkout(checkout, owner, request_id)
            return SubscriptionReference(
                owner, request_id, validated.subscription, validated.customer, validated.id
            )
        elif kind.startswith("invoice."):
            invoice = object_by_id(provider, "invoices", value, "in")
            if invoice["parent"]["type"] != "subscription_details":
                raise ValueError
            expected_customer = invoice["customer"]
            value = invoice["parent"]["subscription_details"]["subscription"]
        subscription = object_by_id(provider, "subscriptions", value, "sub")
        customer = subscription["customer"]
        if not isinstance(customer, str) or not fullmatch(r"cus_[A-Za-z0-9_]+", customer):
            raise ValueError
        if expected_customer is not None and customer != expected_customer:
            raise ValueError
        owner, request_id = metadata_identity(subscription)
        return SubscriptionReference(
            owner=owner,
            request_id=request_id,
            subscription_id=subscription["id"],
            customer_id=customer,
        )
    except (KeyError, TypeError, ValueError):
        raise BillingUnavailable("Vínculo remoto de cobrança inválido.") from None
