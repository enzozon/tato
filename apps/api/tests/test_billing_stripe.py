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


@pytest.mark.parametrize("status", ["open", "complete", "expired"])
def test_retrieve_validates_reference_and_owner_without_creating_checkout(status):
    owner, request_id = uuid4(), uuid4()
    calls = []
    payload = {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": status,
        "payment_status": "unpaid",
        "url": "https://checkout.stripe.com/c/pay/demo" if status == "open" else None,
    }

    def transport(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == "/v1/checkout/sessions/cs_test_demo"
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        assert provider.retrieve_checkout("cs_test_demo", owner, request_id).status == status
        with pytest.raises(BillingUnavailable):
            provider.retrieve_checkout("cs_test_demo/../other", owner, request_id)
        payload["id"] = "cs_test_other"
        with pytest.raises(BillingUnavailable):
            provider.retrieve_checkout("cs_test_demo", owner, request_id)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://[invalid/app/",
        "https://tato.example:bad/app/",
        "https://tato.example:65536/app/",
        "https://tato.example:0/app/",
        "https://@tato.example/app/",
        "\nhttps://tato.example/app/",
        "https://tato.example/ap\tp/",
    ],
)
def test_return_url_rejects_normalized_or_malformed_addresses(url):
    with httpx.Client() as client, pytest.raises(BillingUnavailable) as error:
        StripeSandbox("sk_test_demo", "price_test", client, url)
    assert str(error.value) == "Retorno do checkout inválido."


@pytest.mark.parametrize(
    "mutation",
    [
        {"id": "cs_test_"},
        {"id": "cs_test_demo/../other"},
        {"customer": ""},
        {"customer": "cus_demo/other"},
        {"subscription": ""},
        {"subscription": "sub_demo?expand[]=customer"},
    ],
)
def test_checkout_rejects_malformed_provider_references(mutation):
    owner, request_id = uuid4(), uuid4()
    payload = {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_demo",
        "subscription": "sub_demo",
        **mutation,
    }
    with httpx.Client() as client, pytest.raises(BillingUnavailable):
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        provider.validate_checkout(payload, owner, request_id)


def test_portal_is_test_only_bound_to_customer_and_idempotent():
    request_id = uuid4()
    calls = []

    def transport(request):
        calls.append(request)
        assert request.method == "POST" and request.url.path == "/v1/billing_portal/sessions"
        assert parse_qs(request.content.decode()) == {
            "customer": ["cus_demo"],
            "return_url": ["https://tato.example/app/"],
            "locale": ["pt-BR"],
        }
        return httpx.Response(
            200,
            json={
                "id": "bps_synthetic",
                "object": "billing_portal.session",
                "customer": "cus_demo",
                "return_url": "https://tato.example/app/",
                "livemode": False,
                "url": "https://billing.stripe.com/p/session?secret=test_synthetic",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        assert provider.portal("cus_demo", request_id).startswith("https://billing.stripe.com/")
        provider.portal("cus_demo", request_id)
        with pytest.raises(BillingUnavailable):
            provider.portal("cus_demo/other", request_id)
    assert len(calls) == 2
    assert calls[0].headers["Idempotency-Key"] == calls[1].headers["Idempotency-Key"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"livemode": True},
        {"livemode": 0},
        {"customer": "cus_other"},
        {"return_url": "https://other.example/"},
        {"object": "customer"},
        {"id": "bps_"},
        {"url": None},
        {"url": "https://billing.stripe.com.evil/p/session"},
        {"url": "https://user@billing.stripe.com/p/session"},
        {"url": "http://billing.stripe.com/p/session"},
        {"url": "https://billing.stripe.com:444/p/session"},
        {"url": "https://billing.stripe.com/p/sessionevil"},
        {"url": "https://billing.stripe.com/p/session\n"},
    ],
)
def test_portal_rejects_untrusted_response(mutation):
    payload = {
        "id": "bps_demo",
        "object": "billing_portal.session",
        "customer": "cus_demo",
        "return_url": "https://tato.example/app/",
        "livemode": False,
        "url": "https://billing.stripe.com/p/session?secret=test_synthetic",
        **mutation,
    }
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/").portal(
            "cus_demo", uuid4()
        )
    assert "test_synthetic" not in str(error.value)


def test_portal_never_follows_redirect_or_retries():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(307, headers={"Location": "https://unexpected.example/"})

    with (
        httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as client,
        pytest.raises(BillingUnavailable),
    ):
        StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/").portal(
            "cus_demo", uuid4()
        )
    assert len(calls) == 1
