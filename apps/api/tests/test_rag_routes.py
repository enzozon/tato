from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.main import app
from app.rag import reranking, routes
from app.rag.retrieval import Hit


def test_reranking_only_receives_candidates_and_returns_five(monkeypatch):
    hits = [
        Hit(chunk_id=uuid4(), source="private", source_id="doc", section="s", content=str(i))
        for i in range(25)
    ]
    model = Mock()
    model.rerank.return_value = range(20)
    monkeypatch.setattr(reranking, "cross_encoder", lambda: model)
    result = reranking.rerank("question", hits)
    assert [hit.content for hit in result] == ["19", "18", "17", "16", "15"]
    assert len(model.rerank.call_args.args[1]) == 20
    model.rerank.return_value = [float("nan")] * 20
    with pytest.raises(ValueError):
        reranking.rerank("question", hits)


def test_rag_routes_require_identity():
    with TestClient(app) as client:
        assert client.post("/rag/search", json={"question": "reserva"}).status_code == 401
        assert client.post(f"/rag/documents/{uuid4()}/index").status_code == 401


def test_index_route_contract(monkeypatch):
    app.dependency_overrides[current_identity] = lambda: Identity(id=uuid4())
    app.dependency_overrides[runtime_engine] = lambda: None
    monkeypatch.setattr(routes, "authorize", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "index_private", lambda *args: 2)
    try:
        with TestClient(app) as client:
            response = client.post(f"/rag/documents/{uuid4()}/index")
            assert response.json() == {"chunks": 2}
            assert response.headers["cache-control"] == "no-store"
            monkeypatch.setattr(routes, "index_private", Mock(side_effect=OSError("segredo")))
            failure = client.post(f"/rag/documents/{uuid4()}/index")
            assert failure.status_code == 503
            assert "segredo" not in failure.text
            assert (
                client.post(
                    "/rag/search", json={"question": " ", "user_id": str(uuid4())}
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()
