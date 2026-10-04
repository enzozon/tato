from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.account_service import account_session
from app.agent_mail import deliver_pending
from app.models import Agent, Insight
from tests.integration.test_agent_config import agent_accounts as agent_accounts

pytestmark = pytest.mark.integration


def test_delivery_retries_are_persisted_and_isolated(
    runtime_engine, owners, agent_accounts, monkeypatch
):
    monkeypatch.setenv("AGENT_EMAIL_ENABLED", "true")
    monkeypatch.setenv("RESEND_FREE_TIER_CONFIRMED", "true")
    owner = owners[0]
    with account_session(runtime_engine, owner) as session:
        session.add(
            Agent(user_id=owner, account_id=agent_accounts[0], kind="runway", email_enabled=True)
        )
        session.add(
            Insight(
                user_id=owner,
                agent_kind="runway",
                content_ciphertext=b"test",
                event_key="test",
                email_status="pending",
            )
        )
    calls = []

    def send(user_id, insight_id):
        calls.append((user_id, insight_id))
        return len(calls) > 1

    monkeypatch.setattr("app.agent_mail.send_notice", send)
    assert deliver_pending(runtime_engine, owners[1]) == 0
    assert deliver_pending(runtime_engine, owner) == 0
    assert deliver_pending(runtime_engine, owner) == 0
    assert len(calls) == 1
    with account_session(runtime_engine, owner) as session:
        row = session.exec(select(Insight)).one()
        assert row.email_attempts == 1
        row.email_last_attempt_at = datetime.now(UTC) - timedelta(minutes=3)
        session.add(row)
    assert deliver_pending(runtime_engine, owner) == 1
    assert calls[0] == calls[1]
    assert deliver_pending(runtime_engine, owner) == 0
    with account_session(runtime_engine, owner) as session:
        row = session.exec(select(Insight)).one()
        assert row.email_status == "sent" and row.email_sent_at is not None
