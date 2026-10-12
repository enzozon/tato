from dataclasses import dataclass, field
from datetime import datetime
from re import fullmatch
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.billing_stripe import BillingUnavailable


class AbacatePix(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(pattern=r"^pix_char_[A-Za-z0-9_]+$")
    amount: Literal[3900]
    status: Literal["PENDING", "PAID", "EXPIRED", "CANCELLED"]
    dev_mode: Literal[True] = Field(alias="devMode")
    expires_at: datetime = Field(alias="expiresAt")
    br_code: str = Field(alias="brCode", min_length=1, max_length=4096, repr=False)
    metadata: dict[str, str] = Field(repr=False)


@dataclass
class AbacateSandbox:
    key: str = field(repr=False)
    client: httpx.Client = field(repr=False)

    def __post_init__(self) -> None:
        # O ambiente é escolhido pela chave ANTES de criar qualquer cobrança.
        if not fullmatch(r"dev_[A-Za-z0-9_]+", self.key):
            raise BillingUnavailable("AbacatePay de teste não configurado.")

    def create_pix(self, owner: UUID, request_id: UUID) -> AbacatePix:
        # Sem retry: externalId não tem garantia documentada de idempotência.
        try:
            response = self.client.post(
                "https://api.abacatepay.com/v2/transparents/create",
                headers={"Authorization": f"Bearer {self.key}"},
                json={
                    "method": "PIX",
                    "data": {
                        "amount": 3900,
                        "expiresIn": 3600,
                        "externalId": str(request_id),
                        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
                    },
                },
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload: Any = response.json()
            if (
                not isinstance(payload, dict)
                or payload.get("success") is not True
                or payload.get("error") is not None
                or not isinstance(payload.get("data"), dict)
            ):
                raise ValueError
            data = payload["data"]
            if data.get("devMode") is not True or type(data.get("amount")) is not int:
                raise ValueError
            result = AbacatePix.model_validate(data)
            if (
                result.expires_at.utcoffset() is None
                or result.metadata.get("user_id") != str(owner)
                or result.metadata.get("request_id") != str(request_id)
            ):
                raise ValueError
            return result
        except (httpx.HTTPError, ValueError):
            raise BillingUnavailable(
                "Pix de teste indisponível; reconciliar o pedido antes de repetir."
            ) from None
