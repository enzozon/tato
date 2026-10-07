from uuid import uuid4

from fastapi.testclient import TestClient

from app import billing_routes
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.billing_service import CheckoutResult
from app.billing_stripe import BillingUnavailable
from app.main import app


def test_checkout_auth_configuration_and_public_contract(monkeypatch):
    with TestClient(app) as client:
        assert (
            client.post("/billing/stripe/checkout", json={"request_id": str(uuid4())}).status_code
            == 401
        )
    owner, request_id = uuid4(), uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            monkeypatch.delenv("BILLING_ENABLED", raising=False)
            assert (
                client.post(
                    "/billing/stripe/checkout", json={"request_id": str(request_id)}
                ).status_code
                == 503
            )
            monkeypatch.setenv("BILLING_ENABLED", "true")
            monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
            monkeypatch.setenv("STRIPE_PRICE_ID", "price_test")
            monkeypatch.setenv("BILLING_RETURN_URL", "http://127.0.0.1:3000/app/")

            def success(engine, identity, request, provider):
                assert identity == owner and request == request_id
                return CheckoutResult(
                    request_id=request,
                    status="pending",
                    checkout_url="https://checkout.stripe.com/c/pay/demo",
                )

            monkeypatch.setattr(billing_routes, "checkout", success)
            response = client.post("/billing/stripe/checkout", json={"request_id": str(request_id)})
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert set(response.json()) == {"request_id", "status", "checkout_url"}
            assert (
                client.post(
                    "/billing/stripe/checkout",
                    json={"request_id": str(request_id), "user_id": str(uuid4())},
                ).status_code
                == 422
            )

            def failure(*args):
                raise BillingUnavailable("informacao privada")

            monkeypatch.setattr(billing_routes, "checkout", failure)
            response = client.post("/billing/stripe/checkout", json={"request_id": str(request_id)})
            assert response.status_code == 503 and "privada" not in response.text
    finally:
        app.dependency_overrides.clear()
