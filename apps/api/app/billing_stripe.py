from dataclasses import dataclass, field
from re import fullmatch
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

API_VERSION = "2026-09-30.endive"


class BillingUnavailable(Exception):
    """Mensagem pública sem corpo, URL privada ou credenciais do provedor."""


class StripeCheckout(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    livemode: Literal[False]
    mode: Literal["subscription"]
    currency: Literal["brl"]
    amount_total: Literal[3900]
    client_reference_id: str
    metadata: dict[str, str]
    status: Literal["open", "complete", "expired"]
    payment_status: Literal["paid", "unpaid", "no_payment_required"]
    customer: str | None = None
    subscription: str | None = None
    url: str | None = None


def hosted_url(value: str | None) -> str:
    try:
        url = urlsplit(value or "")
        if (
            url.scheme == "https"
            and url.hostname == "checkout.stripe.com"
            and url.port in {None, 443}
            and url.username is None
            and url.password is None
            and url.path.startswith("/c/pay/")
            and not any(ord(char) < 33 for char in value or "")
        ):
            return value or ""
    except ValueError:
        pass
    raise BillingUnavailable("URL de checkout inválida.")


@dataclass
class StripeSandbox:
    key: str = field(repr=False)
    price_id: str
    client: httpx.Client = field(repr=False)
    return_url: str

    def __post_init__(self) -> None:
        if not self.key.startswith("sk_test_") or not fullmatch(
            r"price_[A-Za-z0-9_]+", self.price_id
        ):
            raise BillingUnavailable("Stripe de teste não configurado.")
        url = urlsplit(self.return_url)
        if (
            url.username
            or url.password
            or url.query
            or url.fragment
            or not url.hostname
            or not (url.scheme == "https" or (url.scheme == "http" and url.hostname == "127.0.0.1"))
        ):
            raise BillingUnavailable("Retorno do checkout inválido.")

    def request(
        self, method: str, path: str, *, data: dict[str, str] | None = None, key: str | None = None
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.key}", "Stripe-Version": API_VERSION}
        if key is not None:
            headers["Idempotency-Key"] = key
        try:
            response = self.client.request(
                method,
                f"https://api.stripe.com/v1/{path}",
                headers=headers,
                data=data,
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("livemode") is not False:
                raise BillingUnavailable("Objeto Stripe fora do modo de teste.")
            return payload
        except (httpx.HTTPError, ValueError):
            raise BillingUnavailable("Stripe de teste indisponível.") from None

    def checkout(self, owner: UUID, request_id: UUID) -> StripeCheckout:
        price = self.request("GET", f"prices/{self.price_id}")
        recurring = price.get("recurring")
        if (
            price.get("id") != self.price_id
            or price.get("active") is not True
            or price.get("currency") != "brl"
            or type(price.get("unit_amount")) is not int
            or price.get("unit_amount") != 3900
            or not isinstance(recurring, dict)
            or recurring.get("interval") != "month"
            or type(recurring.get("interval_count")) is not int
            or recurring.get("interval_count") != 1
        ):
            raise BillingUnavailable("Preço de demonstração inválido.")
        payload = self.request(
            "POST",
            "checkout/sessions",
            key=f"tato-{owner}-{request_id}",
            data={
                "mode": "subscription",
                "line_items[0][price]": self.price_id,
                "line_items[0][quantity]": "1",
                "client_reference_id": str(owner),
                "metadata[user_id]": str(owner),
                "metadata[request_id]": str(request_id),
                "subscription_data[metadata][user_id]": str(owner),
                "subscription_data[metadata][request_id]": str(request_id),
                "success_url": self.return_url,
                "cancel_url": self.return_url,
                "payment_method_types[0]": "card",
                "locale": "pt-BR",
            },
        )
        result = self.validate_checkout(payload, owner, request_id)
        hosted_url(result.url)
        return result

    def validate_checkout(
        self, payload: dict[str, Any], owner: UUID, request_id: UUID
    ) -> StripeCheckout:
        if payload.get("livemode") is not False or type(payload.get("amount_total")) is not int:
            raise BillingUnavailable("Checkout de demonstração inválido.")
        try:
            result = StripeCheckout.model_validate(payload)
        except ValidationError:
            raise BillingUnavailable("Checkout de demonstração inválido.") from None
        if (
            not result.id.startswith("cs_test_")
            or result.client_reference_id != str(owner)
            or result.metadata.get("user_id") != str(owner)
            or result.metadata.get("request_id") != str(request_id)
        ):
            raise BillingUnavailable("Vínculo do checkout inválido.")
        return result

    def retrieve_checkout(self, external_id: str, owner: UUID, request_id: UUID) -> StripeCheckout:
        if not fullmatch(r"cs_test_[A-Za-z0-9_]+", external_id):
            raise BillingUnavailable("Referência de checkout inválida.")
        result = self.validate_checkout(
            self.request("GET", f"checkout/sessions/{external_id}"), owner, request_id
        )
        if result.id != external_id:
            raise BillingUnavailable("Referência de checkout divergente.")
        if result.status == "open":
            hosted_url(result.url)
        return result
