import base64
import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import update
from sqlmodel import select

from app.crypto import decrypt_text, encrypt_text
from app.database import tenant_session
from app.models import Chunk, Document, User
from app.rag import indexing
from app.rag.chunking import TextChunk

pytestmark = pytest.mark.integration


def test_reindex_is_atomic_and_deletion_during_inference_blocks_write(
    runtime_engine, admin_engine, owners, monkeypatch
):
    owner = owners[0]
    key = b"x" * 32
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(key).decode())
    content = "Reserva para emergências."
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
        identifier = document.id
    prepared = ([TextChunk("Reserva", content, 5)], [[1.0] + [0.0] * 383], "test-only")
    monkeypatch.setattr(indexing, "prepare", lambda _: prepared)
    assert indexing.index_private(runtime_engine, owner, identifier) == 1
    assert indexing.index_private(runtime_engine, owner, identifier) == 1
    with tenant_session(runtime_engine, owner) as session:
        chunks = session.exec(select(Chunk)).all()
        assert len(chunks) == 1
        assert decrypt_text(chunks[0].content_ciphertext, key, owner, "chunk") == content
        original_id = chunks[0].id

    def during_inference(_):
        with admin_engine.begin() as connection:
            connection.execute(
                update(User).where(User.id == owner).values(deletion_requested_at=datetime.now(UTC))
            )
        return prepared

    monkeypatch.setattr(indexing, "prepare", during_inference)
    with pytest.raises(ValueError, match="exclusão pendente"):
        indexing.index_private(runtime_engine, owner, identifier)
    with tenant_session(runtime_engine, owner) as session:
        assert session.exec(select(Chunk)).one().id == original_id
