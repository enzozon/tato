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


@pytest.mark.parametrize(
    "next_page",
    [
        "https://evil.test/?after=x",
        "?accountId=other&after=x",
        "?accountId=account-private&after=",
        "?bad",
        "?accountId=account-private&after=x&after=y",
    ],
)
def test_cursor_never_redirects(next_page):
    service = client(lambda _: httpx.Response(200, json={"results": [ROW], "next": next_page}))
    with pytest.raises(PluggyError):
        service.export(ACCOUNT, DAY, DAY)


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_http_errors_are_generic_no_retry(status):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            status, headers={"location": "https://evil.test"}, text="private-canary"
        )

    with pytest.raises(PluggyError) as caught:
        client(respond).accounts("client", "secret", "item")
    assert len(calls) == 1 and "canary" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"results": [ACCOUNT], "totalPages": 2},
        {"results": [ACCOUNT], "total": 2},
        {"results": [ACCOUNT, ACCOUNT]},
        {"results": [{**ACCOUNT, "itemId": "other"}]},
        {"results": []},
    ],
)
def test_incomplete_or_cross_item_accounts_fail(payload):
    service = client(
        lambda r: httpx.Response(200, json={"apiKey": "key"} if r.url.path == "/auth" else payload)
    )
    with pytest.raises(PluggyError):
        service.accounts("client", "secret", "item-private")


def test_response_size_duplicate_and_timeout_fail(monkeypatch):
    import app.meu_pluggy as module

    monkeypatch.setattr(module, "MAX_FILE_BYTES", 100)
    with pytest.raises(PluggyError):
        client(lambda _: httpx.Response(200, content=b"x" * 101)).accounts("c", "s", "i")
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 2 * 1024 * 1024)
    with pytest.raises(PluggyError):
        client(lambda _: httpx.Response(200, json={"results": [ROW, ROW], "next": None})).export(
            ACCOUNT, DAY, DAY
        )

    def timeout(request):
        raise httpx.ReadTimeout("private-canary", request=request)

    with pytest.raises(PluggyError, match="indisponível"):
        client(timeout).accounts("c", "s", "i")


def test_empty_limit_and_repeated_cursor_fail(monkeypatch):
    import app.meu_pluggy as module

    with pytest.raises(PluggyError):
        client(lambda _: httpx.Response(200, json={"results": [], "next": None})).export(
            ACCOUNT, DAY, DAY
        )
    monkeypatch.setattr(module, "MAX_ROWS", 0)
    with pytest.raises(PluggyError, match="5.000"):
        client(lambda _: httpx.Response(200, json={"results": [ROW], "next": None})).export(
            ACCOUNT, DAY, DAY
        )
    monkeypatch.setattr(module, "MAX_ROWS", 5000)
    service = client(
        lambda _: httpx.Response(
            200, json={"results": [], "next": "?accountId=account-private&after=x"}
        )
    )
    with pytest.raises(PluggyError, match="Cursor repetido"):
        service.export(ACCOUNT, DAY, DAY)


def test_renewed_empty_pages_have_request_limit():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200, json={"results": [], "next": f"?accountId=account-private&after={len(calls)}"}
        )

    with pytest.raises(PluggyError, match="20 páginas"):
        client(respond).export(ACCOUNT, DAY, DAY)
    assert len(calls) == 20


@pytest.mark.parametrize("start,end", [(date.min, DAY), (DAY, date.max), (DAY, date(2026, 10, 9))])
def test_invalid_date_window_never_connects(start, end):
    service = client(lambda _: pytest.fail("Sem rede"))
    with pytest.raises(PluggyError):
        service.export(ACCOUNT, start, end)


def test_missing_next_is_not_complete():
    with pytest.raises(PluggyError):
        client(lambda _: httpx.Response(200, json={"results": [ROW]})).export(ACCOUNT, DAY, DAY)


@pytest.mark.parametrize(
    "number", ["1.000000000000000000000000000000000000000000000001", "1e-1000000"]
)
def test_json_decimal_never_rounds_subcents(number):
    raw = json.dumps({"results": [{**ROW, "amount": "NUMBER"}], "next": None}).replace(
        '"NUMBER"', number
    )
    with pytest.raises(PluggyError, match="centavos"):
        client(lambda _: httpx.Response(200, content=raw)).export(ACCOUNT, DAY, DAY)


def test_timestamp_overflow_is_safe():
    service = client(
        lambda _: httpx.Response(
            200, json={"results": [{**ROW, "date": "0001-01-01T00:00:00Z"}], "next": None}
        )
    )
    with pytest.raises(PluggyError, match="Data bancária"):
        service.export(ACCOUNT, DAY, DAY)


@pytest.mark.parametrize("subtype", [None, "LOAN", []])
def test_unknown_subtype_is_rejected(subtype):
    service = client(
        lambda r: httpx.Response(
            200,
            json={"apiKey": "key"}
            if r.url.path == "/auth"
            else {"results": [{**ACCOUNT, "subtype": subtype}]},
        )
    )
    with pytest.raises(PluggyError, match="Subtipo"):
        service.accounts("client", "secret", "item-private")
