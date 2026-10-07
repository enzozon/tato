from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.account_service import account_session
from app.chat_history import month_window
from app.llm import LLMUnavailable
from app.models import Agent, ChatTurn, Document, Subscription, User
from app.usage import consumption
from tests.integration.test_agent_config import agent_accounts as agent_accounts

pytestmark = pytest.mark.integration


def test_usage_counts_accepted_requests_and_distinct_sources_per_owner(
    runtime_engine, admin_engine, owners, agent_accounts, monkeypatch
):
    monkeypatch.setattr("app.usage.check_rate", lambda *args: None)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    start, end = month_window(now)
    for owner, account in zip(owners, agent_accounts, strict=True):
        with account_session(runtime_engine, owner) as session:
            for status, created in [
                ("pending", now),
                ("failed", now),
                ("pending", start - timedelta(seconds=1)),
                ("pending", end),
            ]:
                session.add(
                    ChatTurn(
                        user_id=owner,
                        request_id=uuid4(),
                        created_at=created,
                        request_ciphertext=b"synthetic",
                        status=status,
                        completed_at=now if status == "failed" else None,
                    )
                )
            for index, linked in enumerate([account, account, None]):
                session.add(
                    Document(
                        user_id=owner,
                        account_id=linked,
                        kind="csv" if linked else "note",
                        name_ciphertext=b"synthetic",
                        content_ciphertext=b"synthetic",
                        digest=str(index) * 64,
                    )
                )
            for kind, enabled in [("runway", True), ("anomaly", False)]:
                session.add(Agent(user_id=owner, account_id=account, kind=kind, enabled=enabled))
    free = consumption(runtime_engine, owners[0], now)
    assert free.messages.used == 2 and free.messages.remaining == 198
    assert free.import_sources.used == 1 and free.import_sources.remaining == 0
    assert free.agents.used == 1 and free.agents.remaining == 0
    with Session(admin_engine) as session, session.begin():
        session.add(Subscription(user_id=owners[0], plan="pro", status="active"))
    pro = consumption(runtime_engine, owners[0], now)
    assert pro.messages.limit is None and pro.import_sources.remaining is None
    assert pro.agents.remaining == 2
    assert consumption(runtime_engine, owners[1], now).plan == "free"
    with account_session(runtime_engine, owners[0]) as session:
        user = session.get(User, owners[0])
        user.deletion_requested_at = now
        session.add(user)
    with pytest.raises(LLMUnavailable):
        consumption(runtime_engine, owners[0], now)
