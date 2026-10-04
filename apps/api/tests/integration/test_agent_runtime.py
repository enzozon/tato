import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import update
from sqlmodel import Session, select

from app.account_service import account_session
from app.agent_rules import Signal
from app.agent_runtime import run_agents
from app.crypto import decrypt_text
from app.llm import LLMUnavailable
from app.models import Account, Agent, Goal, Insight, Subscription, User

pytestmark = pytest.mark.integration


def test_agents_are_idempotent_enforce_downgrade_and_delete(
    runtime_engine,
    admin_engine,
    owners,
    monkeypatch,
):
    for name, value in [("DATA_ENCRYPTION_KEY", b"x" * 32), ("DEDUP_HMAC_KEY", b"y" * 32)]:
        monkeypatch.setenv(name, base64.b64encode(value).decode())
    owner = owners[0]
    with account_session(runtime_engine, owner) as session:
        account = Account(
            user_id=owner,
            kind="checking",
            name_ciphertext=b"synthetic",
            opening_date=date(2026, 1, 1),
            opening_balance_cents=10000,
        )
        goal = Goal(user_id=owner, description_ciphertext=b"synthetic", target_cents=10000)
        session.add(account)
        session.add(goal)
        negative = Account(
            user_id=owner,
            kind="checking",
            name_ciphertext=b"synthetic",
            opening_date=date(2026, 1, 1),
            opening_balance_cents=-100,
        )
        session.add(negative)
        session.flush()
        session.add(
            Agent(
                user_id=owner,
                kind="goal",
                account_id=account.id,
                goal_id=goal.id,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            Agent(
                user_id=owner,
                kind="runway",
                account_id=negative.id,
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(
            pool.map(lambda _: run_agents(runtime_engine, owner, date(2026, 10, 4)), range(2))
        )
    assert sorted(counts) == [0, 1]
    with account_session(runtime_engine, owner) as session:
        rows = session.exec(select(Insight)).all()
        assert len(rows) == 1
        decoded = Signal.model_validate_json(
            decrypt_text(rows[0].content_ciphertext, b"x" * 32, owner, "insight")
        )
        assert decoded.facts["balance_cents"] == 10000
    with account_session(runtime_engine, owners[1]) as session:
        assert not session.exec(select(Insight)).all()
    with Session(admin_engine) as session, session.begin():
        session.add(Subscription(user_id=owner, plan="pro", status="active"))
    assert run_agents(runtime_engine, owner, date(2026, 11, 1)) == 1
    with admin_engine.begin() as connection:
        connection.execute(
            update(Subscription).where(Subscription.user_id == owner).values(plan="free")
        )
    assert run_agents(runtime_engine, owner, date(2026, 12, 1)) == 0
    with admin_engine.begin() as connection:
        connection.execute(
            update(User).where(User.id == owner).values(deletion_requested_at=datetime.now(UTC))
        )
    with pytest.raises(LLMUnavailable):
        run_agents(runtime_engine, owner, date(2026, 11, 2))
