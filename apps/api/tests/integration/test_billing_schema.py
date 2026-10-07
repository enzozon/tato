from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlmodel import Session

from app.account_service import account_session
from app.llm import Attempt
from app.llm_service import record_usage
from app.models import BillingCheckout, BillingEvent, LLMUsage, Subscription, User

pytestmark = pytest.mark.integration


def test_billing_metrics_isolation_constraints_and_cascade(
    admin_engine: Engine, runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    records = []
    for owner in owners:
        with account_session(runtime_engine, owner) as session:
            group = [
                BillingCheckout(
                    user_id=owner, provider="stripe", request_id=uuid4(), amount_cents=3900
                ),
                BillingEvent(user_id=owner, provider="stripe", event_id=str(uuid4())),
                LLMUsage(user_id=owner, provider="groq", outcome="error", elapsed_ms=12),
            ]
            session.add_all(group)
            records.append(group)
    with account_session(runtime_engine, owners[0]) as session:
        for own, other in zip(*records, strict=True):
            assert [row.id for row in session.scalars(select(type(own))).all()] == [own.id]
            assert session.get(type(other), other.id) is None
        assert session.get(LLMUsage, records[0][2].id).input_tokens is None
    invalid = [
        (records[0][0], {"amount_cents": 0}),
        (records[0][0], {"provider": "real"}),
        (records[0][0], {"status": "inventado"}),
        (records[0][2], {"input_tokens": -1}),
        (records[0][2], {"output_tokens": -1}),
        (records[0][2], {"elapsed_ms": -1}),
        (records[0][2], {"outcome": "inventado"}),
        (records[1][1], {"event_id": records[0][1].event_id}),
    ]
    for row, values in invalid:
        with pytest.raises(IntegrityError), admin_engine.begin() as connection:
            connection.execute(update(type(row)).where(type(row).id == row.id).values(**values))
    with pytest.raises(ProgrammingError), account_session(runtime_engine, owners[0]) as session:
        session.add(BillingEvent(user_id=owners[1], provider="stripe", event_id=str(uuid4())))
    with admin_engine.begin() as connection:
        connection.execute(delete(User).where(User.id == owners[0]))
    with Session(admin_engine) as session:
        for own, other in zip(*records, strict=True):
            assert session.get(type(own), own.id) is None
            assert session.get(type(other), other.id) is not None


def test_external_references_are_unique_per_provider(
    admin_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    for owner in owners:
        with Session(admin_engine) as session, session.begin():
            session.add(Subscription(user_id=owner))
    with admin_engine.begin() as connection:
        connection.execute(
            update(Subscription)
            .where(Subscription.user_id == owners[0])
            .values(billing_provider="stripe", external_id="sub_test")
        )
    with pytest.raises(IntegrityError), admin_engine.begin() as connection:
        connection.execute(
            update(Subscription)
            .where(Subscription.user_id == owners[1])
            .values(billing_provider="stripe", external_id="sub_test")
        )
    with pytest.raises(IntegrityError), admin_engine.begin() as connection:
        connection.execute(
            update(Subscription)
            .where(Subscription.user_id == owners[1])
            .values(external_id="sem_provedor")
        )


def test_usage_writer_preserves_unknown_tokens_and_blocks_pending_deletion(
    runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    owner = owners[0]
    record_usage(runtime_engine, owner, (Attempt("groq", "error"), Attempt("groq", "ok", 0, 5, 11)))
    with account_session(runtime_engine, owner) as session:
        rows = session.scalars(select(LLMUsage).order_by(LLMUsage.created_at)).all()
        assert len(rows) == 2
        assert rows[0].input_tokens is None
        assert rows[1].input_tokens == 0
        assert rows[1].output_tokens == 5
        user = session.get(User, owner)
        user.deletion_requested_at = datetime.now(UTC)
        session.add(user)
    record_usage(runtime_engine, owner, (Attempt("groq", "ok", 9, 9, 9),))
    with account_session(runtime_engine, owner) as session:
        assert len(session.scalars(select(LLMUsage)).all()) == 2
