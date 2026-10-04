from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import agent_routes as routes
from app.account_routes import runtime_engine
from app.agent_config import AgentView
from app.auth import Identity, current_identity
from app.llm import LLMUnavailable
from app.main import app


@pytest.fixture
def client():
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_agent_contract_hides_internal_fields_and_requires_exact_booleans(client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "configure",
        lambda engine, owner, kind, data: AgentView(id=uuid4(), kind=kind, **data.model_dump()),
    )
    response = client.put("/agents/runway", json={"account_id": str(uuid4())})
    assert response.status_code == 200 and "user_id" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.put("/agents/runway", json={"account_id": str(uuid4()), "enabled": 1}).status_code
        == 422
    )
    assert client.put("/agents/unknown", json={"account_id": str(uuid4())}).status_code == 422
    assert client.get("/insights?limit=101").status_code == 422


def test_read_contracts_and_sanitized_errors(client, monkeypatch):
    for name in ["list_agents", "goals", "insights"]:
        monkeypatch.setattr(routes, name, lambda *args: [])
    for path in ["/agents", "/goals", "/insights"]:
        assert client.get(path).json() == []
    monkeypatch.setattr(routes, "create_goal", lambda *args: uuid4())
    assert (
        client.post("/goals", json={"description": "Reserva", "target_cents": 100}).status_code
        == 201
    )
    monkeypatch.setattr(routes, "mark_read", lambda *args: None)
    assert client.post(f"/insights/{uuid4()}/read").status_code == 204

    def unavailable(*args):
        raise LLMUnavailable("private details")

    monkeypatch.setattr(routes, "list_agents", unavailable)
    response = client.get("/agents")
    assert response.status_code == 409 and "private" not in response.text


def test_internal_route_requires_separate_secret_and_deduplicates_batch(client, monkeypatch):
    monkeypatch.setenv("AGENTS_RUN_TOKEN", "x" * 32)
    owner = str(uuid4())
    payload = {"user_ids": [owner, owner]}
    assert client.post("/internal/agents/run", json=payload).status_code == 401
    monkeypatch.setattr(routes, "run_agents", lambda *args: 1)
    response = client.post(
        "/internal/agents/run", json=payload, headers={"Authorization": "Bearer " + "x" * 32}
    )
    assert response.json() == {"processed": 1, "inserted": 1}
    monkeypatch.delenv("AGENTS_RUN_TOKEN")
    assert client.post("/internal/agents/run", json=payload).status_code == 503


def test_public_agent_routes_require_session():
    with TestClient(app) as client:
        for path in ["/agents", "/goals", "/insights"]:
            assert client.get(path).status_code == 401
