"""Leitura pessoal opt-in; sem escrita no provedor ou no ledger do Tato."""

import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, DecimalException, localcontext
from typing import Any
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.import_parsers import MAX_FILE_BYTES, MAX_ROWS, parse_csv


class PluggyError(ValueError):
    """Falha pública sem dados bancários nem conteúdo da resposta remota."""


def text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 5000:
        raise PluggyError("Resposta bancária inválida.")
    return value


class MeuPluggy:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.key = ""
        self.received = 0

    def request(self, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            with self.client.stream(
                "POST" if path == "/auth" else "GET",
                "https://api.pluggy.ai" + path,
                headers={"X-API-KEY": self.key} if self.key else {},
                follow_redirects=False,
                timeout=20,
                **kwargs,
            ) as response:
                if response.status_code != 200:
                    if response.status_code == 429:
                        raise PluggyError(
                            "Limite do provedor (HTTP 429); aguarde antes de repetir."
                        )
                    if response.status_code >= 500:
                        raise PluggyError(
                            f"Provedor indisponível (HTTP {response.status_code}); "
                            "tente mais tarde."
                        )
                    configuration = {
                        "/auth": "MEU_PLUGGY_CLIENT_ID e MEU_PLUGGY_CLIENT_SECRET da aplicação",
                        "/accounts": "MEU_PLUGGY_ITEM_ID e as permissões da conexão",
                        "/v2/transactions": "MEU_PLUGGY_ACCOUNT_ID e as permissões da conta",
                    }.get(path, "a configuração da aplicação")
                    raise PluggyError(
                        f"Leitura recusada (HTTP {response.status_code}); confira {configuration}."
                    )
                body = bytearray()
                for chunk in response.iter_bytes():
                    self.received += len(chunk)
                    if self.received > MAX_FILE_BYTES:
                        raise PluggyError("Leitura excede 2 MiB; reduza o período.")
                    body.extend(chunk)
                result = json.loads(body, parse_float=Decimal)
                if not isinstance(result, dict):
                    raise ValueError
                return result
        except (
            httpx.HTTPError,
            ValueError,
            UnicodeError,
            DecimalException,
            RecursionError,
        ) as error:
            if isinstance(error, PluggyError):
                raise
            raise PluggyError(
                "Provedor indisponível ou resposta inválida; nenhum CSV criado."
            ) from None

    def accounts(self, client_id: str, secret: str, item_id: str) -> list[dict[str, Any]]:
        self.key = text(
            self.request("/auth", json={"clientId": client_id, "clientSecret": secret}).get(
                "apiKey"
            )
        )
        payload = self.request("/accounts", params={"itemId": item_id})
        accounts = payload.get("results")
        if not isinstance(accounts, list) or not accounts or len(accounts) > 100:
            raise PluggyError("Lista de contas inválida ou vazia.")
        if (
            payload.get("page", 1) != 1
            or payload.get("totalPages", 1) != 1
            or payload.get("total", len(accounts)) != len(accounts)
        ):
            raise PluggyError("Lista de contas incompleta; não há paginação documentada.")
        seen = set()
        for account in accounts:
            if not isinstance(account, dict) or account.get("itemId") != item_id:
                raise PluggyError("Conta não pertence ao item configurado.")
            identifier = text(account.get("id"))
            if identifier in seen:
                raise PluggyError("Contas duplicadas na resposta.")
            seen.add(identifier)
            if (
                account.get("type") not in ("BANK", "CREDIT")
                or account.get("currencyCode") != "BRL"
            ):
                raise PluggyError("Experimento aceita somente contas BANK/CREDIT em BRL.")
            supported = (
                ("BANK", "CHECKING_ACCOUNT"),
                ("BANK", "SAVINGS_ACCOUNT"),
                ("CREDIT", "CREDIT_CARD"),
            )
            if (account.get("type"), account.get("subtype")) not in supported:
                raise PluggyError("Subtipo não suportado; use conta corrente/poupança/cartão.")
        return accounts

    def export(self, account: dict[str, Any], start: date, end: date) -> tuple[bytes, int]:
        if (
            start > end
            or (end - start).days > 366
            or start == date.min
            or end > date.max - timedelta(days=2)
        ):
            raise PluggyError("Período inválido; use até 366 dias.")
        params = {
            "accountId": text(account.get("id")),
            "dateFrom": str(start - timedelta(days=1)),
            # A API não documenta o corte de dateTo; +2 cobre o último dia brasileiro inteiro.
            "dateTo": str(end + timedelta(days=2)),
        }
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Data", "Valor", "Identificador", "Descrição"])
        seen: set[str] = set()
        cursors: set[str] = set()
        pending = 0
        for _page in range(20):
            payload = self.request("/v2/transactions", params=params)
            rows = payload.get("results")
            if not isinstance(rows, list) or len(rows) > 500 or "next" not in payload:
                raise PluggyError("Página bancária inválida.")
            for row in rows:
                if not isinstance(row, dict) or row.get("accountId") != account["id"]:
                    raise PluggyError("Movimentação de outra conta recusada.")
                identifier = text(row.get("id"))
                if identifier in seen or len(seen) >= MAX_ROWS:
                    raise PluggyError("IDs duplicados ou limite de 5.000 movimentos excedido.")
                seen.add(identifier)
                if row.get("status") == "PENDING":
                    pending += 1
                    continue
                if row.get("status") != "POSTED" or row.get("currencyCode") != "BRL":
                    raise PluggyError("Status ou moeda não suportado.")
                try:
                    instant = datetime.fromisoformat(text(row.get("date")))
                    if instant.utcoffset() is None:
                        raise ValueError
                    booked = instant.astimezone(ZoneInfo("America/Sao_Paulo")).date()
                except (ValueError, OverflowError, ZoneInfoNotFoundError):
                    raise PluggyError("Data bancária sem instante/fuso válido.") from None
                if not start <= booked <= end:
                    continue
                amount = row.get("amount")
                if isinstance(amount, bool) or not isinstance(amount, (int, Decimal)):
                    raise PluggyError("Valor bancário inválido.")
                if not Decimal(amount).is_finite() or Decimal(amount).copy_abs() >= 2**63:
                    raise PluggyError("Valor bancário fora do intervalo aceito.")
                digits = Decimal(amount).as_tuple()
                if (
                    isinstance(digits.exponent, int)
                    and digits.exponent < -2
                    and any(digits.digits[digits.exponent + 2 :])
                ):
                    raise PluggyError("Precisão bancária maior que centavos.")
                with localcontext() as context:
                    context.prec = 40
                    cents = Decimal(amount) * 100
                    if cents != cents.to_integral_value():
                        raise PluggyError("Valor bancário fora da precisão ou intervalo aceitos.")
                value = int(cents) * (-1 if account["type"] == "CREDIT" else 1)
                if (
                    not value
                    or not -(2**63) <= value < 2**63
                    or row.get("type") != ("DEBIT" if value < 0 else "CREDIT")
                ):
                    raise PluggyError("Sinal bancário inconsistente com débito/crédito.")
                description = text(row.get("description")).strip()
                if description.startswith(("=", "+", "-", "@")) or any(
                    ord(c) < 32 for c in description
                ):
                    raise PluggyError("Descrição com fórmula/controle recusada; revise a fonte.")
                identity = hashlib.sha256(
                    json.dumps(["pluggy", account["id"], identifier]).encode()
                ).hexdigest()
                writer.writerow(
                    [
                        booked,
                        f"{'-' if value < 0 else ''}{abs(value) // 100},{abs(value) % 100:02d}",
                        "pluggy:" + identity,
                        description,
                    ]
                )
            next_page = payload.get("next")
            if next_page is None:
                break
            if not isinstance(next_page, str) or not next_page.startswith("?"):
                raise PluggyError("Cursor de paginação inválido.")
            try:
                query = parse_qs(next_page[1:], strict_parsing=True, max_num_fields=10)
            except ValueError:
                raise PluggyError("Cursor de paginação inválido.") from None
            after = query.get("after", [])
            if (
                query.get("accountId") != [account["id"]]
                or len(after) != 1
                or not after[0]
                or len(after[0]) > 5000
                or after[0] in cursors
            ):
                raise PluggyError("Cursor repetido ou de outra conta.")
            cursors.add(after[0])
            params["after"] = after[0]
        else:
            raise PluggyError("Leitura excede 20 páginas; reduza o período.")
        content = output.getvalue().encode("utf-8-sig")
        try:
            parse_csv(content)
        except ValueError:
            raise PluggyError(
                "CSV vazio ou fora dos limites de importação; nenhum arquivo criado."
            ) from None
        return content, pending
