from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.billing_stripe import BillingUnavailable, StripeSandbox
from tests.test_billing_payment import payment_chain as payment_chain


@pytest.mark.parametrize(
    "status,invoice_status,refunded,disputed,expected",
    [
        ("active", "paid", 0, False, "active"),
        ("active", "paid", 1, False, "past_due"),
        ("active", "paid", 3900, False, "past_due"),
        ("active", "paid", 0, True, "past_due"),
        ("active", "open", 0, False, "past_due"),
        ("past_due", "paid", 0, False, "past_due"),
        ("canceled", "paid", 0, False, "canceled"),
        ("trialing", "paid", 0, False, "past_due"),
    ],
)
def test_current_subscription_requires_invoice_payment(
    status, invoice_status, refunded, disputed, expected, payment_chain
):
    owner, request_id = uuid4(), uuid4()
    deadline = int(datetime(2026, 11, 7, tzinfo=UTC).timestamp())
    subscription = {
        "id": "sub_demo",
        "customer": "cus_demo",
        "livemode": False,
        "status": status,
        "metadata": {"user_id": str(owner), "request_id": str(request_id)},
        "latest_invoice": "in_demo",
        "items": {
            "has_more": False,
            "data": [
                {
                    "quantity": 1,
                    "current_period_end": deadline,
                    "price": {
                        "id": "price_test",
                        "livemode": False,
                        "currency": "brl",
                        "unit_amount": 3900,
                        "recurring": {"interval": "month", "interval_count": 1},
                    },
                }
            ],
        },
    }
    invoice = {
        "id": "in_demo",
        "customer": "cus_demo",
        "livemode": False,
        "currency": "brl",
        "status": invoice_status,
        "amount_paid": 3900,
        "payments": payment_chain["invoice"]["payments"],
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": "sub_demo"},
        },
    }
    calls = []
    payment_chain["charge"].update(amount_refunded=refunded, disputed=disputed)

    def transport(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/invoices/in_demo":
            assert request.url.params["expand[]"] == "payments"
            payload = invoice
        elif request.url.path == "/v1/payment_intents/pi_demo":
            payload = payment_chain["intent"]
        elif request.url.path == "/v1/charges/ch_demo":
            payload = payment_chain["charge"]
        else:
            payload = subscription
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        result = provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
        assert result.status == expected
        assert result.valid_until == datetime(2026, 11, 7, tzinfo=UTC)
        assert len(calls) == (
            4 if status == "active" and invoice_status == "paid" else 2 if status == "active" else 1
        )
        mutations = [
            {"customer": "cus_other"},
            {"id": "sub_other"},
            {"metadata": {}},
            {"items": None},
            {"status": "inventado"},
            {"livemode": True},
        ]
        original = deepcopy(subscription)
        for mutation in mutations:
            subscription.clear()
            subscription.update(original | mutation)
            with pytest.raises(BillingUnavailable):
                provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
        subscription.clear()
        subscription.update(original)
        if status == "active":
            parent = invoice["parent"]
            invoice["parent"] = None
            with pytest.raises(BillingUnavailable):
                provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
            invoice["parent"] = parent
            if invoice_status == "paid":
                del invoice["payments"]
                with pytest.raises(BillingUnavailable):
                    provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
