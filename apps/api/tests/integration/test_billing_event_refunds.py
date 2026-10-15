from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlmodel import select

from app.account_service import account_session
from app.billing_database import billing_account_session
from app.billing_events import process_event
from app.billing_stripe import StripeSandbox
from app.models import BillingCheckout, BillingEvent, Subscription
from app.plans import user_plan
from tests.integration.test_billing_database_runtime import billing_runtime as billing_runtime

pytestmark = pytest.mark.integration


@pytest.fixture
def history(runtime_engine, billing_runtime, owners):
    owner, other = owners
    request_id, suffix = uuid4(), uuid4().hex
    customer, subscription = f"cus_{suffix}", f"sub_{suffix}"
    checkout = f"cs_test_{suffix}"
    deadline = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    metadata = {"user_id": str(owner), "request_id": str(request_id)}
    objects, months = {}, {}
    for month in ("old", "current"):
        invoice, intent, charge = (f"{prefix}_{month}_{suffix}" for prefix in ("in", "pi", "ch"))
        payment = {
            "id": f"inpay_{month}_{suffix}",
            "object": "invoice_payment",
            "livemode": False,
            "invoice": invoice,
            "status": "paid",
            "currency": "brl",
            "amount_paid": 3900,
            "payment": {"type": "payment_intent", "payment_intent": intent},
        }
        objects[f"/v1/invoices/{invoice}"] = {
            "id": invoice,
            "livemode": False,
            "customer": customer,
            "currency": "brl",
            "status": "paid",
            "amount_paid": 3900,
            "parent": {
                "type": "subscription_details",
                "subscription_details": {"subscription": subscription},
            },
            "payments": {"has_more": False, "data": [payment]},
        }
        objects[f"/v1/payment_intents/{intent}"] = {
            "id": intent,
            "livemode": False,
            "customer": customer,
            "currency": "brl",
            "status": "succeeded",
            "amount_received": 3900,
            "latest_charge": charge,
        }
        objects[f"/v1/charges/{charge}"] = {
            "id": charge,
            "livemode": False,
            "customer": customer,
            "payment_intent": intent,
            "currency": "brl",
            "paid": True,
            "captured": True,
            "amount": 3900,
            "amount_captured": 3900,
            "amount_refunded": 0,
            "disputed": False,
        }
        months[month] = {"invoice": invoice, "intent": intent, "charge": charge, "payment": payment}
    objects[f"/v1/subscriptions/{subscription}"] = {
        "id": subscription,
        "livemode": False,
        "customer": customer,
        "metadata": metadata,
        "status": "active",
        "latest_invoice": months["current"]["invoice"],
        "items": {
            "has_more": False,
            "data": [
                {
                    "quantity": 1,
                    "current_period_end": int(deadline.timestamp()),
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
    objects[f"/v1/checkout/sessions/{checkout}"] = {
        "id": checkout,
        "livemode": False,
        "mode": "subscription",
        "currency": "brl",
        "amount_total": 3900,
        "client_reference_id": str(owner),
        "metadata": metadata,
        "status": "complete",
        "payment_status": "paid",
        "customer": customer,
        "subscription": subscription,
    }
    with account_session(runtime_engine, owner) as session:
        session.add(
            BillingCheckout(
                user_id=owner,
                provider="stripe",
                request_id=request_id,
                external_id=checkout,
                amount_cents=3900,
                status="paid",
            )
        )
    with billing_account_session(billing_runtime, owner) as session:
        session.add(
            Subscription(
                user_id=owner,
                plan="pro",
                status="active",
                billing_provider="stripe",
                external_id=subscription,
                external_customer_id=customer,
                valid_until=deadline,
            )
        )
    return owner, other, objects, months, checkout, deadline


@pytest.mark.parametrize("case", ["old_refund", "current_refund", "current_dispute"])
def test_refund_and_dispute_recompute_latest_invoice_with_persistent_replay(
    history, billing_runtime, case
):
    owner, other, objects, months, checkout, deadline = history
    month = months["old" if case == "old_refund" else "current"]
    charge = objects[f"/v1/charges/{month['charge']}"]
    charge["amount_refunded"] = 3900 if "refund" in case else 0
    charge["disputed"] = case == "current_dispute"
    kind, object_id = "charge.refunded", charge["id"]
    if case == "current_dispute":
        kind, object_id = "charge.dispute.created", f"dp_{uuid4().hex}"
        objects[f"/v1/disputes/{object_id}"] = {
            "id": object_id,
            "livemode": False,
            "charge": charge["id"],
        }
    calls = []

    def transport(request):
        assert request.method == "GET"
        calls.append((request.url.path, dict(request.url.params)))
        if request.url.path == "/v1/invoice_payments":
            assert request.url.params["payment[type]"] == "payment_intent"
            assert request.url.params["payment[payment_intent]"] == month["intent"]
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "has_more": False,
                    "data": [month["payment"]],
                },
            )
        assert request.url.path in objects
        return httpx.Response(200, json=objects[request.url.path])

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = StripeSandbox("sk_test_synthetic", "price_test", client, "https://tato.example/")
        event_id = f"evt_{uuid4().hex}"
        assert process_event(billing_runtime, provider, event_id, kind, object_id)
        assert process_event(billing_runtime, provider, event_id, kind, object_id) is False
    with billing_account_session(billing_runtime, owner) as session:
        subscription = session.exec(select(Subscription)).one()
        assert subscription.status == ("active" if case == "old_refund" else "past_due")
        assert subscription.valid_until == deadline
        assert user_plan(session, owner).name == ("pro" if case == "old_refund" else "free")
        assert session.exec(select(BillingCheckout)).one().status == "paid"
        events = session.exec(select(BillingEvent)).all()
        assert len(events) == 1 and events[0].event_id == event_id
    with billing_account_session(billing_runtime, other) as session:
        assert session.exec(select(Subscription)).all() == []
        assert session.exec(select(BillingEvent)).all() == []
    assert sum(path == f"/v1/checkout/sessions/{checkout}" for path, _ in calls) == 1
    assert (f"/v1/invoices/{months['current']['invoice']}", {"expand[]": "payments"}) in calls
    assert any(path == f"/v1/charges/{months['current']['charge']}" for path, _ in calls)
