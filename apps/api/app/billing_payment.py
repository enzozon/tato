from re import fullmatch
from typing import Any

from app.billing_stripe import BillingUnavailable, StripeSandbox


def payment_clear(provider: StripeSandbox, invoice: dict[str, Any], customer_id: str) -> bool:
    """Confere o pagamento atual; reembolso/disputa suspende a concessão automática."""
    try:
        invoice_id = invoice["id"]
        payments = invoice["payments"]
        rows = payments["data"]
        if (
            not fullmatch(r"in_[A-Za-z0-9_]+", invoice_id)
            or not fullmatch(r"cus_[A-Za-z0-9_]+", customer_id)
            or not isinstance(rows, list)
            or len(rows) != 1
            or payments["has_more"] is not False
        ):
            raise ValueError
        payment = rows[0]
        if (
            not fullmatch(r"inpay_[A-Za-z0-9_]+", payment["id"])
            or payment["object"] != "invoice_payment"
            or payment["livemode"] is not False
            or payment["invoice"] != invoice_id
            or payment["status"] != "paid"
            or payment["currency"] != "brl"
            or type(payment["amount_paid"]) is not int
            or payment["amount_paid"] != 3900
            or payment["payment"]["type"] != "payment_intent"
        ):
            raise ValueError
        intent_id = payment["payment"]["payment_intent"]
        if not fullmatch(r"pi_[A-Za-z0-9_]+", intent_id):
            raise ValueError
        intent = provider.request("GET", f"payment_intents/{intent_id}")
        if (
            intent["id"] != intent_id
            or intent["customer"] != customer_id
            or intent["currency"] != "brl"
            or intent["status"] != "succeeded"
            or type(intent["amount_received"]) is not int
            or intent["amount_received"] != 3900
        ):
            raise ValueError
        charge_id = intent["latest_charge"]
        if not fullmatch(r"ch_[A-Za-z0-9_]+", charge_id):
            raise ValueError
        charge = provider.request("GET", f"charges/{charge_id}")
        if (
            charge["id"] != charge_id
            or charge["customer"] != customer_id
            or charge["payment_intent"] != intent_id
            or charge["currency"] != "brl"
            or charge["paid"] is not True
            or charge["captured"] is not True
            or type(charge["amount"]) is not int
            or charge["amount"] != 3900
            or type(charge["amount_captured"]) is not int
            or charge["amount_captured"] != 3900
            or type(charge["amount_refunded"]) is not int
            or not 0 <= charge["amount_refunded"] <= 3900
            or type(charge["disputed"]) is not bool
        ):
            raise ValueError
        return charge["amount_refunded"] == 0 and charge["disputed"] is False
    except (KeyError, TypeError, IndexError, ValueError):
        raise BillingUnavailable("Contrato do pagamento de teste inválido.") from None
