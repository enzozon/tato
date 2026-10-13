from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session

from app.models import BillingCheckout, BillingEvent, Subscription, User

pytestmark = pytest.mark.integration
BILLING_MODELS = (Subscription, BillingCheckout, BillingEvent)


@contextmanager
def billing_session(engine: Engine, owner: UUID | None) -> Iterator[Session]:
    # SET LOCAL exercita o papel real sem criar outra credencial de teste.
    with Session(engine, expire_on_commit=False) as session, session.begin():
        session.execute(text("SET LOCAL ROLE tato_billing"))
        session.execute(
            text("SELECT set_config('app.user_id', :owner, true)"),
            {"owner": str(owner) if owner else ""},
        )
        yield session


def billing_record(model: type, owner: UUID):
    if model is Subscription:
        return Subscription(user_id=owner, plan="pro")
    if model is BillingCheckout:
        return BillingCheckout(
            user_id=owner, provider="stripe", request_id=uuid4(), amount_cents=3900
        )
    return BillingEvent(user_id=owner, provider="stripe", event_id=str(uuid4()))


def test_billing_role_has_only_approved_privileges(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, "
                "rolreplication, rolinherit FROM pg_roles WHERE rolname = 'tato_billing'"
            )
        ).one()
        assert tuple(role) == (False,) * 6
        assert (
            connection.scalar(text("SELECT pg_has_role('tato_app', 'tato_billing', 'MEMBER')"))
            is False
        )
        assert (
            connection.scalar(text("SELECT pg_has_role('tato_billing', 'tato_app', 'MEMBER')"))
            is False
        )
        for table in ("users", "subscriptions", "billing_checkouts", "billing_events"):
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            ):
                expected = privilege == "SELECT" or (
                    table != "users" and privilege in ("INSERT", "UPDATE", "DELETE")
                )
                assert (
                    connection.scalar(
                        text("SELECT has_table_privilege('tato_billing', :table, :privilege)"),
                        {"table": table, "privilege": privilege},
                    )
                    is expected
                )
        for table in (
            "accounts",
            "categories",
            "transactions",
            "rules",
            "goals",
            "documents",
            "chunks",
            "chat_turns",
            "insights",
            "knowledge_chunks",
            "llm_usage",
        ):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert (
                    connection.scalar(
                        text("SELECT has_table_privilege('tato_billing', :table, :privilege)"),
                        {"table": table, "privilege": privilege},
                    )
                    is False
                )


@pytest.mark.parametrize("model", BILLING_MODELS)
def test_billing_role_crud_is_tenant_scoped(
    admin_engine: Engine, owners: tuple[UUID, UUID], model: type
) -> None:
    records = []
    for owner in owners:
        with billing_session(admin_engine, owner) as session:
            record = billing_record(model, owner)
            session.add(record)
            session.flush()
            records.append(record)
    own, other = records
    with billing_session(admin_engine, owners[0]) as session:
        assert session.scalar(text("SELECT current_user")) == "tato_billing"
        assert [row.id for row in session.scalars(select(model))] == [own.id]
        assert session.get(model, other.id) is None
        changed = session.execute(update(model).where(model.id == own.id).values(user_id=owners[0]))
        assert changed.rowcount == 1
        assert (
            session.execute(
                update(model).where(model.id == other.id).values(user_id=owners[0])
            ).rowcount
            == 0
        )
        assert session.execute(delete(model).where(model.id == other.id)).rowcount == 0
    with billing_session(admin_engine, None) as session:
        assert session.scalars(select(model)).all() == []
    with pytest.raises(ProgrammingError), billing_session(admin_engine, owners[0]) as session:
        session.add(billing_record(model, owners[1]))
    with pytest.raises(ProgrammingError), billing_session(admin_engine, owners[0]) as session:
        session.execute(update(model).where(model.id == own.id).values(user_id=owners[1]))
    with billing_session(admin_engine, owners[0]) as session:
        assert session.execute(delete(model).where(model.id == own.id)).rowcount == 1
    with billing_session(admin_engine, owners[1]) as session:
        assert session.get(model, other.id) is not None


def test_billing_role_can_only_read_own_user(
    admin_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    with billing_session(admin_engine, owners[0]) as session:
        assert [user.id for user in session.scalars(select(User))] == [owners[0]]
        assert session.get(User, owners[1]) is None
    with billing_session(admin_engine, None) as session:
        assert session.scalars(select(User)).all() == []
    for statement in (
        update(User).where(User.id == owners[0]).values(deletion_requested_at=None),
        delete(User).where(User.id == owners[0]),
    ):
        with pytest.raises(ProgrammingError), billing_session(admin_engine, owners[0]) as session:
            session.execute(statement)
    with pytest.raises(ProgrammingError), billing_session(admin_engine, owners[0]) as session:
        session.add(User(id=uuid4()))


@pytest.mark.parametrize("table", ["transactions", "documents", "chat_turns", "llm_usage"])
def test_billing_role_cannot_read_private_data(
    admin_engine: Engine, owners: tuple[UUID, UUID], table: str
) -> None:
    with pytest.raises(ProgrammingError), billing_session(admin_engine, owners[0]) as session:
        session.execute(text(f"SELECT * FROM {table} LIMIT 0"))
