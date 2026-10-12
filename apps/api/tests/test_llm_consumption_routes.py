from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app import usage
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.llm import LLMUnavailable
from app.main import app


def test_llm_consumption_requires_identity_and_preserves_unknown_tokens(monkeypatch):
    with TestClient(app) as client:
        assert client.get("/me/llm-usage").status_code == 401
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    now = datetime(2026, 10, 12, tzinfo=UTC)

    def measured(engine, identity, moment):
        assert identity == owner and moment.tzinfo == UTC
        return usage.LLMConsumption(
            period_start=now,
            period_end=now,
            attempts=1,
            input_tokens=None,
            output_tokens=0,
            unknown_input_attempts=1,
            unknown_output_attempts=0,
            elapsed_ms=10,
        )

    try:
        monkeypatch.setattr(usage, "llm_consumption", measured)
        with TestClient(app) as client:
            response = client.get("/me/llm-usage")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.json()["input_tokens"] is None
            assert response.json()["output_tokens"] == 0
            assert set(response.json()) == set(usage.LLMConsumption.model_fields)

            def unavailable(*args):
                raise LLMUnavailable("synthetic-private-error")

            monkeypatch.setattr(usage, "llm_consumption", unavailable)
            response = client.get("/me/llm-usage")
            assert response.status_code == 409
            assert "synthetic-private-error" not in response.text
    finally:
        app.dependency_overrides.clear()
