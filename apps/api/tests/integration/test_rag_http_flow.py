import base64
import hashlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.account_routes import runtime_engine as engine_dependency
from app.auth import Identity, current_identity
from app.crypto import encrypt_text
from app.database import tenant_session
from app.main import app
from app.models import Document, User
from app.rag import indexing, routes
from app.rag.chunking import TextChunk

pytestmark = pytest.mark.integration


def test_http_search_isolates_sources_and_rechecks_deletion(
    runtime_engine, admin_engine, owners, monkeypatch
):
    first, second = owners
    key = b"r" * 32
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(key).decode())
    monkeypatch.setattr(routes, "check_rate", lambda *args: None)
    vector = [1.0] + [0.0] * 383
    monkeypatch.setattr(routes, "embed", lambda *args, **kwargs: [vector])
    monkeypatch.setattr(routes, "encoder", lambda: (None, None, "http-test"))
    monkeypatch.setattr(
        indexing, "prepare", lambda text: ([TextChunk("Nota", text, 5)], [vector], "http-test")
    )
    identifiers = []
    for owner, content in [(first, "Reserva própria."), (second, "Segredo de outro usuário.")]:
        with tenant_session(runtime_engine, owner) as session:
            document = Document(
                user_id=owner,
                kind="note",
                digest=hashlib.sha256(content.encode()).hexdigest(),
                name_ciphertext=encrypt_text("nota", key, owner, "document_name"),
                content_ciphertext=encrypt_text(content, key, owner, "document"),
            )
            session.add(document)
            session.flush()
            identifiers.append(document.id)
        indexing.index_private(runtime_engine, owner, identifiers[-1])
    app.dependency_overrides[current_identity] = lambda: Identity(id=first)
    app.dependency_overrides[engine_dependency] = lambda: runtime_engine
    try:
        with TestClient(app) as client:
            response = client.post("/rag/search", json={"question": "Reserva", "rerank": False})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert [hit["source_id"] for hit in response.json()] == [str(identifiers[0])]
            assert "Segredo" not in response.text
            assert client.post(f"/rag/documents/{identifiers[1]}/index").status_code == 422

            def delete_during_reranking(question, hits):
                assert all(hit.source_id == str(identifiers[0]) for hit in hits)
                with admin_engine.begin() as connection:
                    connection.execute(
                        update(User)
                        .where(User.id == first)
                        .values(deletion_requested_at=datetime.now(UTC))
                    )
                return hits

            monkeypatch.setattr(routes, "rerank", delete_during_reranking)
            blocked = client.post("/rag/search", json={"question": "Reserva"})
            assert blocked.status_code == 409
            assert "Reserva própria" not in blocked.text
    finally:
        app.dependency_overrides.clear()
