from uuid import uuid4

import httpx
import pytest

from app.billing_cleanup import customer_request, expire_checkout
from app.billing_stripe import API_VERSION, BillingUnavailable, StripeSandbox


def provider(client):
    return StripeSandbox("sk_test_synthetic", "price_test", client, "https://tato.example/app/")


def checkout_payload(owner, request_id, **changes):
    return {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "open",
        "payment_status": "unpaid",
        "url": "https://checkout.stripe.com/c/pay/demo",
        **changes,
    }


@pytest.mark.parametrize("deleted", [False, True])
def test_customer_supports_alive_and_deleted_without_generic_relaxation(deleted):
    calls = []

    def transport(request):
        calls.append(request)
        assert request.headers["Stripe-Version"] == API_VERSION
        assert request.url.path == "/v1/customers/cus_demo"
        payload = {"id": "cus_demo", "object": "customer"}
        payload.update(
            {"deleted": True} if deleted or request.method == "DELETE" else {"livemode": False}
        )
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        stripe = provider(client)
        assert customer_request(stripe, "GET", "cus_demo") is deleted
        if not deleted:
            assert customer_request(stripe, "DELETE", "cus_demo")
        with pytest.raises(BillingUnavailable):
            stripe.request("DELETE", "customers/cus_demo")
    assert len(calls) == (2 if deleted else 3)


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "cus_other", "object": "customer", "deleted": True},
        {"id": "cus_demo", "object": "subscription", "deleted": True},
        {"id": "cus_demo", "object": "customer", "deleted": 1},
        {"id": "cus_demo", "object": "customer", "livemode": True},
        {"id": "cus_demo", "object": "customer", "livemode": 0},
        {"id": "cus_demo", "object": "customer"},
        {"id": "cus_demo", "object": "customer", "deleted": True, "livemode": True},
        [],
    ],
)
def test_invalid_customer_never_passes(payload):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as client,
        pytest.raises(BillingUnavailable),
    ):
        customer_request(provider(client), "GET", "cus_demo")


def test_customer_request_rejects_bad_mode_reference_redirect_and_private_error():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(307, text="privado", headers={"Location": "https://evil.example"})

    with httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as client:
        stripe = provider(client)
        for method, reference in [("POST", "cus_demo"), ("GET", "cus_demo/other")]:
            with pytest.raises(BillingUnavailable):
                customer_request(stripe, method, reference)
        with pytest.raises(BillingUnavailable) as error:
            customer_request(stripe, "GET", "cus_demo")
        assert "privado" not in str(error.value)
        stripe.key = "sk_live_synthetic"
        with pytest.raises(BillingUnavailable):
            customer_request(stripe, "GET", "cus_demo")
    assert len(calls) == 1


@pytest.mark.parametrize("status", ["expired", "complete", "open"])
def test_expire_handles_race_but_preserves_open_failure(status):
    owner, request_id = uuid4(), uuid4()
    calls = []

    def transport(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(400, text="privado")
        return httpx.Response(200, json=checkout_payload(owner, request_id, status=status))

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        stripe = provider(client)
        remote = stripe.validate_checkout(checkout_payload(owner, request_id), owner, request_id)
        if status == "open":
            with pytest.raises(BillingUnavailable):
                expire_checkout(stripe, remote, owner, request_id)
        else:
            assert expire_checkout(stripe, remote, owner, request_id).status == status
    assert calls == ["POST", "GET"]


def test_expire_requires_expected_id_and_expired_response():
    owner, request_id = uuid4(), uuid4()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=checkout_payload(owner, request_id, id="cs_test_other", status="expired")
            )
        )
    ) as client:
        stripe = provider(client)
        remote = stripe.validate_checkout(checkout_payload(owner, request_id), owner, request_id)
        with pytest.raises(BillingUnavailable):
            expire_checkout(stripe, remote, owner, request_id)
