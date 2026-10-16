import importlib.util
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("smoke_stripe", Path("scripts/smoke_stripe.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
CLIENT = httpx.Client


@pytest.fixture(autouse=True)
def synthetic_configuration(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_synthetic")
    monkeypatch.setenv("BILLING_RETURN_URL", "http://127.0.0.1:3000/app/")
    monkeypatch.setenv("BILLING_ENABLED", "false")


def test_requires_opt_in_before_client(monkeypatch, capsys):
    monkeypatch.setattr(smoke.httpx, "Client", lambda **kwargs: pytest.fail("Sem cliente HTTP"))
    assert smoke.main([]) == 2
    assert "--confirm-test-mode" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "BILLING_RETURN_URL"])
def test_missing_configuration_never_connects(monkeypatch, name):
    monkeypatch.delenv(name)
    monkeypatch.setattr(smoke.httpx, "Client", lambda **kwargs: pytest.fail("Sem cliente HTTP"))
    assert smoke.main(["--confirm-test-mode"]) == 1


@pytest.mark.parametrize(
    "case", ["valid", "live_key", "live_price", "wrong_price", "http", "timeout"]
)
def test_read_only_contract_and_safe_output(monkeypatch, capsys, case):
    calls = []
    if case == "live_key":
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_private-canary")

    def respond(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url == "https://api.stripe.com/v1/prices/price_synthetic"
        if case == "timeout":
            raise httpx.ReadTimeout("private-canary", request=request)
        if case == "http":
            return httpx.Response(401, text="private-canary")
        return httpx.Response(
            200,
            json={
                "id": "price_synthetic",
                "livemode": case == "live_price",
                "active": True,
                "currency": "brl",
                "unit_amount": 4000 if case == "wrong_price" else 3900,
                "recurring": {"interval": "month", "interval_count": 1},
            },
        )

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        return CLIENT(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(smoke.httpx, "Client", client)
    assert smoke.main(["--confirm-test-mode"]) == (0 if case == "valid" else 1)
    assert len(calls) == (0 if case == "live_key" else 1)
    output = capsys.readouterr().out
    assert "private-canary" not in output
    assert "sk_test_synthetic" not in output and "price_synthetic" not in output
    if case == "valid":
        assert "webhook e pagamento não exercitados" in output


def test_redirect_is_not_followed(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example/"})

    monkeypatch.setattr(
        smoke.httpx,
        "Client",
        lambda **kwargs: CLIENT(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert smoke.main(["--confirm-test-mode"]) == 1
    assert len(calls) == 1
