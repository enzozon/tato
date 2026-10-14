import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app import billing_routes
from app.billing_stripe import API_VERSION
from app.main import app

SECRET = "whsec_" + "synthetic" * 8


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(billing_routes, "billing_engine", Mock(return_value=None))
    monkeypatch.setattr(billing_routes, "provider_for", Mock(return_value=None))
    processor = Mock()
    monkeypatch.setattr(billing_routes, "process_event", processor)
    return processor


def test_chunked_event_stops_at_body_limit_before_authentication(configured, monkeypatch):
    signature = Mock()
    monkeypatch.setattr(billing_routes, "stripe_signature", signature)
    consumed = []

    async def chunks():
        for size in (32768, 32768, 1, 32768):
            consumed.append(size)
            yield b"x" * size

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/billing/stripe/webhook", content=chunks())

    response = asyncio.run(send())
    assert "content-length" not in response.request.headers
    assert response.request.headers["transfer-encoding"] == "chunked"
    assert response.status_code == 413
    assert consumed == [32768, 32768, 1]
    signature.assert_not_called()
    configured.assert_not_called()
    billing_routes.billing_engine.assert_not_called()
    billing_routes.provider_for.assert_not_called()


@pytest.mark.parametrize("failure", [PermissionError, SQLAlchemyError])
@pytest.mark.parametrize("origin", ["billing_engine", "process_event"])
def test_storage_failure_is_retryable_private_and_not_cacheable(
    configured, monkeypatch, failure, origin
):
    private = "synthetic-private-storage-connection"
    failing = Mock(side_effect=failure(private))
    monkeypatch.setattr(billing_routes, origin, failing)
    body = json.dumps(
        {
            "id": "evt_transport",
            "type": "invoice.paid",
            "api_version": API_VERSION,
            "livemode": False,
            "data": {"object": {"id": "in_transport"}},
        }
    ).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/billing/stripe/webhook",
                content=body,
                headers={"Stripe-Signature": f"t={timestamp},v1={digest}"},
            )

    response = asyncio.run(send())
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {"detail": "Armazenamento temporariamente indisponível."}
    assert private not in response.text
    failing.assert_called_once()
    if origin == "billing_engine":
        configured.assert_not_called()
