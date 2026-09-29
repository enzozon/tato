import hashlib

import pytest

from app.crypto import encrypt_text
from app.database import tenant_session
from app.models import Chunk, Document
from app.rag.retrieval import search

pytestmark = pytest.mark.integration


def test_private_vector_and_fts_never_retrieve_another_owner(runtime_engine, owners):
    identifiers = []
    vector = [1.0] + [0.0] * 383
    for owner, content in zip(owners, ["reserva alfa", "segredo exclusivo beta"], strict=True):
        with tenant_session(runtime_engine, owner) as session:
            document = Document(
                user_id=owner,
                kind="note",
                digest=hashlib.sha256(str(owner).encode()).hexdigest(),
                name_ciphertext=encrypt_text("nota", b"x" * 32, owner, "document_name"),
                content_ciphertext=encrypt_text(content, b"x" * 32, owner, "document"),
            )
            session.add(document)
            session.flush()
            chunk = Chunk(
                user_id=owner,
                document_id=document.id,
                position=0,
                embedding=vector,
                embedding_model="test-only",
                content_ciphertext=encrypt_text(content, b"x" * 32, owner, "chunk"),
            )
            session.add(chunk)
            session.flush()
            identifiers.append(chunk.id)
    with tenant_session(runtime_engine, owners[0]) as session:
        hits = search(session, owners[0], "segredo exclusivo beta", vector, "test-only", b"x" * 32)
        assert [hit.chunk_id for hit in hits] == [identifiers[0]]
        assert all("beta" not in hit.content for hit in hits)
        # Mesmo com owner incorreto no chamador, RLS impede ler o outro usuário.
        assert search(session, owners[1], "beta", vector, "test-only", b"x" * 32) == []
    with tenant_session(runtime_engine, owners[1]) as session:
        hits = search(session, owners[1], "segredo exclusivo beta", vector, "test-only", b"x" * 32)
        assert [hit.chunk_id for hit in hits] == [identifiers[1]]
        assert hits[0].score == 2 / 61
