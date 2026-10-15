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
    status: Literal["PENDING", "PAID", "EXPIRED", "CANCELLED", "REFUNDED"]
    dev_mode: Literal[True] = Field(alias="devMode")
    expires_at: datetime = Field(alias="expiresAt")
    br_code: str = Field(alias="brCode", min_length=1, max_length=4096, repr=False)
    metadata: dict[str, str] = Field(repr=False)


def validated_pix(data: Any, owner: UUID, request_id: UUID) -> AbacatePix:
    if (
        not isinstance(data, dict)
        or data.get("devMode") is not True
        or type(data.get("amount")) is not int
    ):
        raise ValueError
    result = AbacatePix.model_validate(data)
    if (
        result.expires_at.utcoffset() is None
        or result.metadata.get("user_id") != str(owner)
        or result.metadata.get("request_id") != str(request_id)
    ):
        raise ValueError
    return result


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
            return validated_pix(payload["data"], owner, request_id)
        except (httpx.HTTPError, ValueError):
            raise BillingUnavailable(
                "Pix de teste indisponível; reconciliar o pedido antes de repetir."
            ) from None

    def find_pix(self, owner: UUID, request_id: UUID) -> AbacatePix | None:
        # None não prova ausência de efeito remoto nem permite repetir o POST.
        params = {"method": "PIX", "externalId": str(request_id), "limit": "100"}
        cursors: set[str] = set()
        found: AbacatePix | None = None
        try:
            # shortcut: no máximo 2.000 registros; ampliar apenas com medição de uso.
            for _ in range(20):
                response = self.client.get(
                    "https://api.abacatepay.com/v2/transparents/list",
                    headers={"Authorization": f"Bearer {self.key}"},
                    params=params,
                    timeout=10,
                    follow_redirects=False,
                )
                response.raise_for_status()
                payload: Any = response.json()
                if (
                    not isinstance(payload, dict)
                    or payload.get("success") is not True
                    or payload.get("error") is not None
                    or not isinstance(payload.get("data"), list)
                    or len(payload["data"]) > 100
                    or not isinstance(payload.get("pagination"), dict)
                ):
                    raise ValueError
                for data in payload["data"]:
                    result = validated_pix(data, owner, request_id)
                    if found is not None:
                        raise ValueError
                    found = result
                pagination = payload["pagination"]
                if pagination.get("hasMore") is False:
                    return found
                cursor = pagination.get("next")
                if (
                    pagination.get("hasMore") is not True
                    or not isinstance(cursor, str)
                    or not fullmatch(r"pix_char_[A-Za-z0-9_]{1,128}", cursor)
                    or cursor in cursors
                ):
                    raise ValueError
                cursors.add(cursor)
                params["after"] = cursor
            raise ValueError
        except (httpx.HTTPError, ValueError):
            raise BillingUnavailable("Reconciliação Pix de teste indisponível.") from None
