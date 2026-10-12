import json
from uuid import uuid4

import httpx
import pytest

from app.billing_abacate import AbacateSandbox
from app.billing_stripe import BillingUnavailable


def test_pix_selects_sandbox_before_request_and_binds_exact_amount_to_owner():
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.abacatepay.com/v2/transparents/create"
        assert request.headers["Authorization"] == "Bearer dev_synthetic"
        data = json.loads(request.content)
        assert data["method"] == "PIX"
        assert data["data"]["amount"] == 3900
        assert data["data"]["externalId"] == str(request_id)
        assert set(data["data"]) == {"amount", "expiresIn", "externalId", "metadata"}
        return httpx.Response(
            200,
            json={
                "success": True,
                "error": None,
                "data": {
                    "id": "pix_char_synthetic",
                    "amount": 3900,
                    "status": "PENDING",
                    "devMode": True,
                    "expiresAt": "2026-10-12T23:00:00Z",
                    "brCode": "synthetic-private-pix-code",
                    "metadata": data["data"]["metadata"],
                    "customer": {"email": "never-retain@example.test"},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = AbacateSandbox("dev_synthetic", client)
        result = provider.create_pix(owner, request_id)
    assert len(calls) == 1
    assert "dev_synthetic" not in repr(provider)
    assert result.amount == 3900 and result.status == "PENDING"
    assert "private-pix-code" not in repr(result)
    assert "never-retain" not in result.model_dump_json()


@pytest.mark.parametrize("key", ["prod_synthetic", "", "dev_", "dev_x\n", "sk_test_other"])
def test_production_or_unknown_key_is_rejected_without_network(key):
    def unexpected(request):
        pytest.fail("A configuração inválida não pode enviar uma requisição.")

    with (
        httpx.Client(transport=httpx.MockTransport(unexpected)) as client,
        pytest.raises(BillingUnavailable),
    ):
        AbacateSandbox(key, client)


@pytest.mark.parametrize(
    "mutation",
    [
        {"devMode": False},
        {"devMode": 1},
        {"amount": 3900.0},
        {"amount": 39},
        {"id": "bole_other"},
        {"status": "UNKNOWN"},
        {"metadata": {}},
        {"expiresAt": "2026-10-12T23:00:00"},
    ],
)
def test_pix_rejects_untrusted_remote_data(mutation):
    owner, request_id = uuid4(), uuid4()
    data = {
        "id": "pix_char_synthetic",
        "amount": 3900,
        "status": "PENDING",
        "devMode": True,
        "expiresAt": "2026-10-12T23:00:00Z",
        "brCode": "synthetic-code",
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        **mutation,
    }
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"success": True, "error": None, "data": data})
            )
        ) as client,
        pytest.raises(BillingUnavailable),
    ):
        AbacateSandbox("dev_synthetic", client).create_pix(owner, request_id)


def test_timeout_is_sanitized_and_never_automatically_retries_creation():
    calls = []

    def transport(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-private-body", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(transport)) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        AbacateSandbox("dev_synthetic", client).create_pix(uuid4(), uuid4())
    assert len(calls) == 1
    assert "secret-private-body" not in str(error.value)
    assert "reconciliar" in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="secret-private-body"),
        httpx.Response(307, headers={"Location": "https://unexpected.example"}),
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"success": False, "error": "secret-private-body"}),
        httpx.Response(200, json={"success": True, "data": []}),
    ],
)
def test_remote_errors_are_sanitized_without_redirects(response):
    calls = []

    def transport(request):
        calls.append(request)
        return response

    with (
        httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        AbacateSandbox("dev_synthetic", client).create_pix(uuid4(), uuid4())
    assert len(calls) == 1
    assert "secret-private-body" not in str(error.value)
