from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session

from app.database import tenant_session
from app.models import KnowledgeChunk

pytestmark = pytest.mark.integration


def test_public_fts_and_runtime_read_only(admin_engine, runtime_engine, owners):
    identifier = uuid4()
    try:
        with Session(admin_engine) as session, session.begin():
            session.add(
                KnowledgeChunk(
                    id=identifier,
                    slug=str(identifier),
                    position=0,
                    section="Reserva",
                    content="Reservas para emergências e imprevistos.",
                    content_digest="0" * 64,
                    embedding=[1.0] + [0.0] * 383,
                    embedding_model="test-only",
                )
            )
        for owner in owners:
            with tenant_session(runtime_engine, owner) as session:
                match = session.execute(
                    text(
                        "SELECT id FROM knowledge_chunks WHERE id=:id "
                        "AND search_vector @@ plainto_tsquery('portuguese', 'emergência')"
                    ),
                    {"id": identifier},
                ).scalar_one()
                assert match == identifier
        with (
            pytest.raises(ProgrammingError) as error,
            tenant_session(runtime_engine, owners[0]) as session,
        ):
            session.execute(
                text("UPDATE knowledge_chunks SET content=content WHERE id=:id"), {"id": identifier}
            )
        assert error.value.orig.sqlstate == "42501"
    finally:
        with admin_engine.begin() as connection:
            connection.execute(delete(KnowledgeChunk).where(KnowledgeChunk.id == identifier))
