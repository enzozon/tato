from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import pytest

from app.billing_stripe import API_VERSION, BillingUnavailable, StripeSandbox, hosted_url


def test_checkout_is_test_only_idempotent_and_bound_to_owner():
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request)
        assert request.headers["Stripe-Version"] == API_VERSION
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "price_test",
                    "active": True,
                    "livemode": False,
                    "currency": "brl",
                    "unit_amount": 3900,
                    "recurring": {"interval": "month", "interval_count": 1},
                },
            )
        data = parse_qs(request.content.decode())
        assert data["metadata[user_id]"] == [str(owner)]
        assert data["subscription_data[metadata][request_id]"] == [str(request_id)]
        assert data["line_items[0][quantity]"] == ["1"]
        assert "email" not in str(data)
        return httpx.Response(
            200,
            json={
                "id": "cs_test_demo",
                "livemode": False,
                "mode": "subscription",
                "currency": "brl",
                "amount_total": 3900,
                "client_reference_id": str(owner),
                "metadata": {"user_id": str(owner), "request_id": str(request_id)},
                "status": "open",
                "payment_status": "unpaid",
                "url": "https://checkout.stripe.com/c/pay/cs_test_demo#fragment",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "http://127.0.0.1:3000/app/")
        first = provider.checkout(owner, request_id)
        provider.checkout(owner, request_id)
    assert first.amount_total == 3900
    assert calls[1].headers["Idempotency-Key"] == calls[3].headers["Idempotency-Key"]
    assert "sk_test_demo" not in repr(provider)
    with pytest.raises(BillingUnavailable):
        provider.validate_checkout(first.model_dump(), uuid4(), request_id)


@pytest.mark.parametrize(
    "mutation",
    [
        {"livemode": True},
        {"unit_amount": 3900.0},
        {"unit_amount": 4000},
        {"currency": "usd"},
        {"active": False},
        {"recurring": {"interval": "year"}},
        {"recurring": None},
    ],
)
def test_bad_price_never_creates_checkout(mutation):
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "id": "price_test",
                "active": True,
                "livemode": False,
                "currency": "brl",
                "unit_amount": 3900,
                "recurring": {"interval": "month", "interval_count": 1},
                **mutation,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        with pytest.raises(BillingUnavailable):
            provider.checkout(uuid4(), uuid4())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://checkout.stripe.com.evil/c/pay/x",
        "https://user@checkout.stripe.com/c/pay/x",
        "http://checkout.stripe.com/c/pay/x",
        "https://checkout.stripe.com:444/c/pay/x",
        "https://checkout.stripe.com/c/pay/x\n",
        None,
    ],
)
def test_hosted_url_rejects_untrusted_destination(url):
    with pytest.raises(BillingUnavailable):
        hosted_url(url)


def test_configuration_and_remote_errors_are_sanitized():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(500, text="privado"))
    ) as client:
        with pytest.raises(BillingUnavailable):
            StripeSandbox("sk_live_demo", "price_test", client, "https://tato.example/app/")
        with pytest.raises(BillingUnavailable):
            StripeSandbox("sk_test_demo", "price_test", client, "https://user@tato.example/app/")
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        with pytest.raises(BillingUnavailable) as error:
            provider.checkout(uuid4(), uuid4())
        assert "privado" not in str(error.value)
