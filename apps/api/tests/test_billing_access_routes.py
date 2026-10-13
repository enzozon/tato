from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import billing_routes
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.billing_access import BillingStatus, PortalResult
from app.billing_stripe import BillingUnavailable
from app.main import app


def test_billing_access_requires_authentication():
    with TestClient(app) as client:
        assert client.get("/billing/status").status_code == 401
        assert (
            client.post("/billing/stripe/portal", json={"request_id": str(uuid4())}).status_code
            == 401
        )


@pytest.mark.parametrize("configured", [False, True])
def test_billing_status_is_private_and_configuration_gated(monkeypatch, configured):
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo" if configured else "sk_live_forbidden")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test")
    monkeypatch.setenv("BILLING_RETURN_URL", "http://127.0.0.1:3000/app/")

    def result(engine, identity, enabled):
        assert identity == owner and enabled is configured
        return BillingStatus(enabled=enabled, can_checkout=enabled, can_portal=False)

    monkeypatch.setattr(billing_routes, "status", result)
    try:
        with TestClient(app) as client:
            response = client.get("/billing/status")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.json() == {
                "enabled": configured,
                "mode": "test",
                "can_checkout": configured,
                "can_portal": False,
                "pending_request_id": None,
            }
    finally:
        app.dependency_overrides.clear()


def test_portal_public_contract_rejects_customer_input_and_sanitizes_errors(monkeypatch):
    owner, request_id = uuid4(), uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    monkeypatch.setenv("BILLING_ENABLED", "false")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test")
    monkeypatch.setenv("BILLING_RETURN_URL", "http://127.0.0.1:3000/app/")

    def success(engine, identity, request, provider):
        assert identity == owner and request == request_id
        return PortalResult(portal_url="https://billing.stripe.com/p/session/demo")

    monkeypatch.setattr(billing_routes, "portal", success)
    try:
        with TestClient(app) as client:
            body = {"request_id": str(request_id)}
            assert client.post("/billing/stripe/portal", json=body).status_code == 503
            monkeypatch.setenv("BILLING_ENABLED", "true")
            response = client.post("/billing/stripe/portal", json=body)
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert set(response.json()) == {"portal_url"}
            assert (
                client.post(
                    "/billing/stripe/portal", json=body | {"customer_id": "cus_other"}
                ).status_code
                == 422
            )

            def failure(*args):
                raise BillingUnavailable("segredo sintético")

            monkeypatch.setattr(billing_routes, "portal", failure)
            response = client.post("/billing/stripe/portal", json=body)
            assert response.status_code == 503 and "sintético" not in response.text
    finally:
        app.dependency_overrides.clear()
