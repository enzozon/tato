from uuid import UUID

import pytest
from sqlalchemy import Engine, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col

from app.database import tenant_session
from app.models import Account, Category, Chunk, Document, Goal, Rule, Transaction, User
from app.repositories import document_chunks
from app.seed_data import demo_records

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(admin_engine: Engine, owners: tuple[UUID, UUID]):
    records = [demo_records(owner, b"x" * 32, b"y" * 32) for owner in owners]
    with admin_engine.begin() as connection:
        for group in records:
            for record in group[1:]:
                connection.execute(insert(type(record)).values(**record.model_dump()))
    return records


def test_constraints_reject_invalid_money_and_foreign_ownership(
    admin_engine: Engine, graph
) -> None:
    first, other = ({type(row): row for row in group} for group in graph)
    cases = [
        (Transaction, {"amount_cents": 1}, "23514"),
        (Transaction, {"amount_cents": 0}, "23514"),
        (Transaction, {"dedup_key": "invalido"}, "23514"),
        (Account, {"currency": "USD"}, "23514"),
        (Goal, {"target_cents": 0}, "23514"),
        (Chunk, {"position": -1}, "23514"),
        (Transaction, {"account_id": other[Account].id}, "23503"),
        (Transaction, {"category_id": other[Category].id}, "23503"),
        (Rule, {"category_id": other[Category].id}, "23503"),
        (Chunk, {"document_id": other[Document].id}, "23503"),
    ]
    for model, values, state in cases:
        with pytest.raises(IntegrityError) as error, admin_engine.begin() as connection:
            connection.execute(update(model).where(model.id == first[model].id).values(**values))
        assert error.value.orig.sqlstate == state
    with pytest.raises(IntegrityError), admin_engine.begin() as connection:
        connection.execute(delete(Account).where(Account.id == first[Account].id))


def test_unique_constraints_resist_duplicate_rows(admin_engine: Engine, graph) -> None:
    from uuid import uuid4

    for row in graph[0]:
        if isinstance(row, (Category, Transaction, Chunk)):
            with pytest.raises(IntegrityError) as error, admin_engine.begin() as connection:
                connection.execute(insert(type(row)).values(**(row.model_dump() | {"id": uuid4()})))
            assert error.value.orig.sqlstate == "23505"


def test_vectors_and_every_table_are_isolated(runtime_engine: Engine, graph) -> None:
    first, other = graph
    owner = first[0].id
    with tenant_session(runtime_engine, owner) as session:
        for row in first:
            visible = session.scalars(select(type(row))).all()
            assert [item.id for item in visible] == [row.id]
        chunk = next(row for row in first if isinstance(row, Chunk))
        session.execute(update(Chunk).where(Chunk.id == chunk.id).values(embedding=[1.0] * 384))
        session.flush()
        # Sem filtro explícito: a RLS também protege o caminho vetorial.
        nearest = session.scalars(
            select(Chunk).order_by(col(Chunk.embedding).cosine_distance([1.0] * 384))
        ).all()
        assert [item.id for item in nearest] == [chunk.id]
        assert len(nearest[0].embedding) == 384
        assert [item.id for item in document_chunks(session, owner, chunk.document_id)] == [
            chunk.id
        ]
        assert document_chunks(session, other[0].id, chunk.document_id) == []


def test_cascade_removes_documents_and_user_data(admin_engine: Engine, graph) -> None:
    first, other = graph
    document = next(row for row in first if isinstance(row, Document))
    with admin_engine.begin() as connection:
        connection.execute(delete(Document).where(Document.id == document.id))
    with Session(admin_engine) as session:
        assert session.scalars(select(Chunk).where(Chunk.user_id == first[0].id)).all() == []
    with admin_engine.begin() as connection:
        connection.execute(delete(User).where(User.id == first[0].id))
    with Session(admin_engine) as session:
        for row in first:
            assert session.get(type(row), row.id) is None
        for row in other:
            assert session.get(type(row), row.id) is not None


def test_rls_is_forced_on_all_domain_tables(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
                "AND relname <> 'alembic_version'"
            )
        ).all()
    assert len(rows) == 10
    assert all(enabled and forced for enabled, forced in rows)
