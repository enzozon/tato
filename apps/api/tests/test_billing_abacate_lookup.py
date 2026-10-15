from uuid import uuid4

import httpx
import pytest

from app.billing_abacate import AbacateSandbox
from app.billing_stripe import BillingUnavailable


def pix(owner, request_id, **changes):
    return {
        "id": "pix_char_synthetic",
        "amount": 3900,
        "status": "REFUNDED",
        "devMode": True,
        "expiresAt": "2026-10-15T23:00:00Z",
        "brCode": "synthetic-private-code",
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        **changes,
    }


def page(data, **pagination):
    return {
        "success": True,
        "error": None,
        "data": data,
        "pagination": {"hasMore": False, **pagination},
    }


def test_lookup_checks_all_pages_without_creating_or_exposing_private_data():
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.path == "/v2/transparents/list"
        assert request.url.params["method"] == "PIX"
        assert request.url.params["externalId"] == str(request_id)
        assert request.url.params["limit"] == "100"
        assert request.headers["Authorization"] == "Bearer dev_synthetic"
        if len(calls) == 1:
            return httpx.Response(
                200, json=page([pix(owner, request_id)], hasMore=True, next="opaque:cursor/1+=")
            )
        assert request.url.params["after"] == "opaque:cursor/1+="
        return httpx.Response(200, json=page([]))

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = AbacateSandbox("dev_synthetic", client).find_pix(owner, request_id)
    assert result is not None and result.status == "REFUNDED"
    assert len(calls) == 2
    assert "private-code" not in repr(result)


def test_lookup_absent_returns_none_without_creation():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(200, json=page([]))

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert AbacateSandbox("dev_synthetic", client).find_pix(uuid4(), uuid4()) is None
    assert len(calls) == 1 and calls[0].method == "GET"


@pytest.mark.parametrize(
    "mutation",
    [
        {"amount": 3900.0},
        {"amount": True},
        {"amount": 3901},
        {"devMode": 1},
        {"devMode": False},
        {"metadata": {"user_id": str(uuid4()), "request_id": str(uuid4())}},
        {"metadata": {"user_id": 1}},
        {"expiresAt": "2026-10-15T23:00:00"},
        {"id": "card_other"},
        {"status": "UNKNOWN"},
    ],
)
def test_lookup_refuses_untrusted_remote_binding(mutation):
    owner, request_id = uuid4(), uuid4()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=page([pix(owner, request_id, **mutation)]))
            )
        ) as client,
        pytest.raises(BillingUnavailable),
    ):
        AbacateSandbox("dev_synthetic", client).find_pix(owner, request_id)


@pytest.mark.parametrize(
    "failure",
    ["duplicate", "cursor", "missing", "boolean", "exhausted", "control", "unicode", "long"],
)
def test_lookup_refuses_ambiguous_or_incomplete_listing(failure):
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request)
        if failure == "duplicate":
            payload = page([pix(owner, request_id), pix(owner, request_id)])
        elif failure == "missing":
            payload = {"data": [], "success": True}
        elif failure == "boolean":
            payload = page([], hasMore=0)
        elif failure in {"control", "unicode", "long"}:
            cursor = {"control": "opaque\n", "unicode": "opacoç", "long": "x" * 257}[failure]
            payload = page([], hasMore=True, next=cursor)
        else:
            cursor = "pix_char_repeated" if failure == "cursor" else f"pix_char_{len(calls)}"
            payload = page([], hasMore=True, next=cursor)
        return httpx.Response(200, json=payload)

    with (
        httpx.Client(transport=httpx.MockTransport(transport)) as client,
        pytest.raises(BillingUnavailable),
    ):
        AbacateSandbox("dev_synthetic", client).find_pix(owner, request_id)
    assert len(calls) <= 20


@pytest.mark.parametrize("kind", ["timeout", "redirect", "json", "error"])
def test_lookup_remote_failures_are_sanitized_without_retry_or_redirect(kind):
    calls = []

    def transport(request):
        calls.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("private-secret", request=request)
        if kind == "redirect":
            return httpx.Response(307, headers={"Location": "https://example.test/private-secret"})
        if kind == "json":
            return httpx.Response(200, text="private-secret")
        return httpx.Response(200, json={"success": False, "error": "private-secret"})

    with (
        httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        AbacateSandbox("dev_synthetic", client).find_pix(uuid4(), uuid4())
    assert len(calls) == 1
    assert "private-secret" not in str(error.value)
