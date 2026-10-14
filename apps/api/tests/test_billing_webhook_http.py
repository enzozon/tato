import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import billing_routes
from app.billing_stripe import API_VERSION, BillingUnavailable
from app.main import app

SECRET = "whsec_" + "synthetic" * 8


def headers(body, delta=0):
    timestamp = str(int(time.time()) + delta)
    digest = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}"}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(billing_routes, "billing_engine", lambda: None)
    monkeypatch.setattr(billing_routes, "provider_for", lambda client: None)
    processor = Mock()
    monkeypatch.setattr(billing_routes, "process_event", processor)
    return processor


@pytest.mark.parametrize(
    "defect", [None, "signature", "replay", "live", "version", "malformed", "unknown"]
)
def test_webhook_authenticates_original_bytes_and_rejects_unsafe_contract(configured, defect):
    event = {
        "id": "evt_demo",
        "type": "invoice.paid",
        "api_version": API_VERSION,
        "livemode": False,
        "data": {"object": {"id": "in_demo"}},
    }
    if defect == "live":
        event["livemode"] = True
    if defect == "version":
        event["api_version"] = "2019-02-19"
    if defect == "unknown":
        event["type"] = "customer.created"
    body = b"not-json" if defect == "malformed" else json.dumps(event).encode()
    signed = headers(body, -301 if defect == "replay" else 0)
    if defect == "signature":
        body += b" "
    with TestClient(app) as client:
        response = client.post("/billing/stripe/webhook", content=body, headers=signed)
    assert response.status_code == (200 if defect in {None, "unknown"} else 400)
    if defect is None:
        configured.assert_called_once_with(None, None, "evt_demo", "invoice.paid", "in_demo")
        assert response.headers["Cache-Control"] == "no-store"
    else:
        configured.assert_not_called()


def test_webhook_limits_body_and_retries_transient_failure(configured, monkeypatch):
    with TestClient(app) as client:
        assert client.post("/billing/stripe/webhook", content=b"x" * 65537).status_code == 413
        body = json.dumps(
            {
                "id": "evt_demo",
                "type": "invoice.paid",
                "api_version": API_VERSION,
                "livemode": False,
                "data": {"object": {"id": "in_demo"}},
            }
        ).encode()
        configured.side_effect = BillingUnavailable("synthetic-private-information")
        response = client.post("/billing/stripe/webhook", content=body, headers=headers(body))
        assert response.status_code == 503 and "private" not in response.text
        monkeypatch.setenv("BILLING_ENABLED", "false")
        assert (
            client.post("/billing/stripe/webhook", content=body, headers=headers(body)).status_code
            == 503
        )
