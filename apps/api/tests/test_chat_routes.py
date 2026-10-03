from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import chat_routes as routes
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.chat_contracts import ChatReply
from app.main import app


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[current_identity] = lambda: Identity(id=uuid4())
    app.dependency_overrides[runtime_engine] = lambda: None
    monkeypatch.setattr(routes, "authorize", lambda *a, **k: None)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_chat_json_and_sse_share_validated_reply(client, monkeypatch):
    reply = ChatReply(turn_id=uuid4(), intent="conversation", message="Olá\nevent: erro falso")
    monkeypatch.setattr(routes, "respond", lambda *a: reply)
    body = {"request_id": str(uuid4()), "question": "oi"}
    assert client.post("/chat", json=body).json() == reply.model_dump(mode="json")
    stream = client.post("/chat/stream", json=body)
    assert stream.status_code == 200 and stream.headers["cache-control"] == "no-store"
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert [part.splitlines()[0] for part in stream.text.strip().split("\n\n")] == [
        "event: status",
        "event: reply",
        "event: done",
    ]


def test_chat_errors_never_echo_private_details(client, monkeypatch):
    def fail(*args):
        raise ValueError("conteúdo pessoal nunca exposto")

    monkeypatch.setattr(routes, "respond", fail)
    body = {"request_id": str(uuid4()), "question": "oi"}
    response = client.post("/chat", json=body)
    assert response.status_code == 503 and "pessoal" not in response.text
    response = client.post("/chat/stream", json=body)
    assert "event: error" in response.text and "pessoal" not in response.text
    assert "event: reply" not in response.text


def test_confirm_requires_explicit_true_and_history_contract(client, monkeypatch):
    reply = ChatReply(turn_id=uuid4(), intent="entry", message="Registrado")
    monkeypatch.setattr(routes, "confirm_entry", lambda *a: reply)
    assert client.post(f"/chat/{reply.turn_id}/confirm", json={"confirm": True}).status_code == 200
    for value in [False, "true", 1, 1.0]:
        assert (
            client.post(f"/chat/{reply.turn_id}/confirm", json={"confirm": value}).status_code
            == 422
        )
    monkeypatch.setattr(routes, "load_key", lambda *a: b"x" * 32)
    monkeypatch.setattr(routes, "recent_history", lambda *a: [])
    assert client.get("/chat").json() == []


def test_chat_routes_auth_and_openapi():
    with TestClient(app) as client:
        assert client.post("/chat", json={}).status_code == 401
        assert client.post("/chat/stream", json={}).status_code == 401
        assert client.get("/chat").status_code == 401
    schema = app.openapi()
    for path in ["/chat", "/chat/stream", "/chat/{turn_id}/confirm"]:
        assert schema["paths"][path]["post"]["security"] == [{"HTTPBearer": []}]
    assert (
        "text/event-stream"
        in schema["paths"]["/chat/stream"]["post"]["responses"]["200"]["content"]
    )
