from uuid import uuid4

import httpx
import pytest

from app.billing_resolution import resolve_subscription
from app.billing_stripe import BillingUnavailable, StripeSandbox


def test_dispute_resolves_through_current_invoice_without_list_livemode():
    owner, request_id = uuid4(), uuid4()
    responses = {
        "/v1/disputes/dp_demo": {"id": "dp_demo", "charge": "ch_demo"},
        "/v1/charges/ch_demo": {
            "id": "ch_demo",
            "payment_intent": "pi_demo",
            "customer": "cus_demo",
        },
        "/v1/payment_intents/pi_demo": {"id": "pi_demo", "customer": "cus_demo"},
        "/v1/invoices/in_demo": {
            "id": "in_demo",
            "customer": "cus_demo",
            "parent": {"subscription_details": {"subscription": "sub_demo"}},
        },
        "/v1/subscriptions/sub_demo": {
            "id": "sub_demo",
            "customer": "cus_demo",
            "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        },
    }
    listing = {
        "object": "list",
        "has_more": False,
        "data": [
            {
                "livemode": False,
                "invoice": "in_demo",
                "payment": {"type": "payment_intent", "payment_intent": "pi_demo"},
            }
        ],
    }
    calls = []

    def transport(request):
        calls.append(request)
        if request.url.path == "/v1/invoice_payments":
            assert request.url.params["payment[type]"] == "payment_intent"
            assert request.url.params["payment[payment_intent]"] == "pi_demo"
            return httpx.Response(200, json=listing)
        return httpx.Response(200, json={"livemode": False, **responses[request.url.path]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_demo", client, "https://tato.example/")
        result = resolve_subscription(provider, "charge.dispute.created", "dp_demo")
        assert result.owner == owner and result.request_id == request_id
        assert result.subscription_id == "sub_demo" and result.customer_id == "cus_demo"
        for mutation in [{"has_more": True}, {"data": []}, {"data": [{"livemode": True}]}]:
            original = listing.copy()
            listing.update(mutation)
            with pytest.raises(BillingUnavailable):
                resolve_subscription(provider, "charge.refunded", "ch_demo")
            listing.clear()
            listing.update(original)
        with pytest.raises(BillingUnavailable):
            resolve_subscription(provider, "charge.dispute.created", "dp_x/../other")
    assert len(calls) == 15


def test_expired_checkout_without_subscription_still_resolves_owned_reservation():
    owner, request_id = uuid4(), uuid4()
    payload = {
        "id": "cs_test_demo",
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "status": "expired",
        "payment_status": "unpaid",
        "customer": None,
        "subscription": None,
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        provider = StripeSandbox("sk_test_demo", "price_demo", client, "https://tato.example/")
        reference = resolve_subscription(provider, "checkout.session.expired", "cs_test_demo")
        assert reference.owner == owner and reference.checkout_id == "cs_test_demo"
        assert reference.subscription_id is None
        payload["client_reference_id"] = str(uuid4())
        with pytest.raises(BillingUnavailable):
            resolve_subscription(provider, "checkout.session.expired", "cs_test_demo")
