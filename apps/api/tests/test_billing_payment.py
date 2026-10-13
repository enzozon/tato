from copy import deepcopy

import httpx
import pytest

from app.billing_payment import payment_clear
from app.billing_stripe import BillingUnavailable, StripeSandbox


@pytest.fixture
def payment_chain():
    return {
        "invoice": {
            "id": "in_demo",
            "payments": {
                "has_more": False,
                "data": [
                    {
                        "id": "inpay_demo",
                        "object": "invoice_payment",
                        "livemode": False,
                        "invoice": "in_demo",
                        "status": "paid",
                        "currency": "brl",
                        "amount_paid": 3900,
                        "payment": {"type": "payment_intent", "payment_intent": "pi_demo"},
                    }
                ],
            },
        },
        "intent": {
            "id": "pi_demo",
            "livemode": False,
            "customer": "cus_demo",
            "currency": "brl",
            "status": "succeeded",
            "amount_received": 3900,
            "latest_charge": "ch_demo",
        },
        "charge": {
            "id": "ch_demo",
            "livemode": False,
            "customer": "cus_demo",
            "payment_intent": "pi_demo",
            "currency": "brl",
            "paid": True,
            "captured": True,
            "amount": 3900,
            "amount_captured": 3900,
            "amount_refunded": 0,
            "disputed": False,
        },
    }


@pytest.mark.parametrize(
    "refunded,disputed,expected",
    [(0, False, True), (1, False, False), (3900, False, False), (0, True, False)],
)
def test_payment_checks_current_charge_for_refund_or_dispute(
    payment_chain, refunded, disputed, expected
):
    payment_chain["charge"].update(amount_refunded=refunded, disputed=disputed)
    calls = []

    def transport(request):
        calls.append(request.url.path)
        key = "intent" if request.url.path == "/v1/payment_intents/pi_demo" else "charge"
        return httpx.Response(200, json=payment_chain[key])

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        assert payment_clear(provider, payment_chain["invoice"], "cus_demo") is expected
    assert calls == ["/v1/payment_intents/pi_demo", "/v1/charges/ch_demo"]


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("invoice", {"id": "in_demo/other"}),
        ("invoice", {"payments": {"data": [], "has_more": False}}),
        ("invoice", {"payments": None}),
        ("payment", {"invoice": "in_other"}),
        ("payment", {"livemode": 0}),
        ("payment", {"amount_paid": 3900.0}),
        ("payment", {"status": "open"}),
        ("payment", {"payment": {"type": "payment_intent", "payment_intent": "pi_x?y"}}),
        ("intent", {"customer": "cus_other"}),
        ("intent", {"status": "requires_capture"}),
        ("intent", {"amount_received": "3900"}),
        ("intent", {"latest_charge": None}),
        ("charge", {"livemode": True}),
        ("charge", {"payment_intent": "pi_other"}),
        ("charge", {"customer": "cus_other"}),
        ("charge", {"paid": 1}),
        ("charge", {"amount_captured": 3899}),
        ("charge", {"amount_refunded": -1}),
        ("charge", {"amount_refunded": 3901}),
        ("charge", {"amount_refunded": False}),
        ("charge", {"disputed": 0}),
    ],
)
def test_payment_rejects_bad_contract_without_grant(payment_chain, target, mutation):
    if target == "payment":
        payment_chain["invoice"]["payments"]["data"][0].update(mutation)
    else:
        payment_chain[target].update(mutation)

    def transport(request):
        key = "intent" if "payment_intents" in request.url.path else "charge"
        return httpx.Response(200, json=payment_chain[key])

    with (
        httpx.Client(transport=httpx.MockTransport(transport)) as client,
        pytest.raises(BillingUnavailable) as error,
    ):
        payment_clear(
            StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/"),
            payment_chain["invoice"],
            "cus_demo",
        )
    assert "cus_other" not in str(error.value)


def test_payment_rejects_incomplete_or_multiple_invoice_payments(payment_chain):
    invoice = payment_chain["invoice"]
    with httpx.Client() as client:
        provider = StripeSandbox("sk_test_demo", "price_test", client, "https://tato.example/app/")
        invoice["payments"]["has_more"] = True
        with pytest.raises(BillingUnavailable):
            payment_clear(provider, invoice, "cus_demo")
        invoice["payments"]["has_more"] = False
        invoice["payments"]["data"].append(deepcopy(invoice["payments"]["data"][0]))
        with pytest.raises(BillingUnavailable):
            payment_clear(provider, invoice, "cus_demo")
