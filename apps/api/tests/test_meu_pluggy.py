import json
from datetime import date

import httpx
import pytest

from app.import_parsers import parse_csv
from app.meu_pluggy import MeuPluggy, PluggyError

DAY = date(2026, 10, 10)
ACCOUNT = {
    "id": "account-private",
    "itemId": "item-private",
    "type": "BANK",
    "currencyCode": "BRL",
    "subtype": "CHECKING_ACCOUNT",
}
ROW = {
    "id": "txn-private",
    "accountId": "account-private",
    "currencyCode": "BRL",
    "date": "2026-10-11T01:00:00Z",
    "amount": -12.34,
    "type": "DEBIT",
    "status": "POSTED",
    "description": "Descrição sintética",
}


def client(handler):
    return MeuPluggy(httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))


def test_auth_accounts_and_cursor_roundtrip():
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "api.pluggy.ai"
        if request.url.path == "/auth":
            assert request.method == "POST"
            assert json.loads(request.content) == {"clientId": "client", "clientSecret": "secret"}
            return httpx.Response(200, json={"apiKey": "private-key"})
        assert request.method == "GET" and request.headers["X-API-KEY"] == "private-key"
        if request.url.path == "/accounts":
            assert request.url.params["itemId"] == "item-private"
            return httpx.Response(200, json={"results": [ACCOUNT], "total": 1, "totalPages": 1})
        assert request.url.path == "/v2/transactions"
        assert request.url.params["dateFrom"] == "2026-10-09"
        assert request.url.params["dateTo"] == "2026-10-11"
        if "after" not in request.url.params:
            return httpx.Response(
                200, json={"results": [ROW], "next": "?accountId=account-private&after=a%2Bb"}
            )
        assert request.url.params["after"] == "a+b"
        return httpx.Response(
            200,
            json={
                "results": [
                    {**ROW, "id": "pending", "status": "PENDING"},
                    {**ROW, "id": "outside", "date": "2026-10-11T04:00:00Z"},
                ],
                "next": None,
            },
        )

    service = client(respond)
    accounts = service.accounts("client", "secret", "item-private")
    content, pending = service.export(accounts[0], DAY, DAY)
    entries = parse_csv(content)
    assert pending == 1 and len(entries) == 1
    assert entries[0].amount_cents == -1234 and entries[0].booked_on == DAY
    assert b"private" not in content and entries[0].description == ROW["description"]
    assert len(calls) == 4


@pytest.mark.parametrize(
    "kind,amount,flow,expected",
    [
        ("BANK", 1.23, "CREDIT", 123),
        ("CREDIT", 1.23, "DEBIT", -123),
        ("CREDIT", -1.23, "CREDIT", 123),
    ],
)
def test_signs_are_normalized(kind, amount, flow, expected):
    service = client(
        lambda _: httpx.Response(
            200, json={"results": [{**ROW, "amount": amount, "type": flow}], "next": None}
        )
    )
    content, _ = service.export({**ACCOUNT, "type": kind}, DAY, DAY)
    assert parse_csv(content)[0].amount_cents == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"amount": 1.001},
        {"amount": True},
        {"amount": "12.34"},
        {"amount": 1e100},
        {"currencyCode": "USD"},
        {"type": "CREDIT"},
        {"accountId": "other"},
        {"date": "2026-10-10"},
        {"date": "2026-10-10T10:00:00"},
        {"status": "UNKNOWN"},
        {"description": " =SUM(1;2)"},
        {"description": "a\tb"},
        {"id": ""},
    ],
)
def test_invalid_transactions_fail_without_csv(changes):
    service = client(
        lambda _: httpx.Response(200, json={"results": [{**ROW, **changes}], "next": None})
    )
    with pytest.raises(PluggyError) as caught:
        service.export(ACCOUNT, DAY, DAY)
    assert "private" not in str(caught.value)
