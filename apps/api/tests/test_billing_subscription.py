from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.billing_stripe import BillingUnavailable, StripeSandbox


@pytest.mark.parametrize(
    "status,invoice_status,expected",
    [
        ("active", "paid", "active"),
        ("active", "open", "past_due"),
        ("past_due", "paid", "past_due"),
        ("canceled", "paid", "canceled"),
        ("trialing", "paid", "past_due"),
    ],
)
def test_current_subscription_requires_invoice_payment(status, invoice_status, expected):
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
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": "sub_demo"},
        },
    }
    calls = []

    def transport(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=invoice if "invoices" in request.url.path else subscription)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        result = provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
        assert result.status == expected
        assert result.valid_until == datetime(2026, 11, 7, tzinfo=UTC)
        assert len(calls) == (2 if status == "active" else 1)
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
            invoice["parent"] = None
            with pytest.raises(BillingUnavailable):
                provider.subscription_state("sub_demo", owner, request_id, "cus_demo")
