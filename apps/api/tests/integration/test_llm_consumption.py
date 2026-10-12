from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.account_service import account_session
from app.chat_history import month_window
from app.llm import LLMUnavailable
from app.models import LLMUsage, User
from app.usage import llm_consumption

pytestmark = pytest.mark.integration


def test_llm_consumption_isolated_monthly_and_distinguishes_unknown_from_zero(
    runtime_engine, owners, monkeypatch
):
    monkeypatch.setattr("app.usage.check_rate", lambda *args: None)
    now = datetime(2026, 10, 12, tzinfo=UTC)
    start, end = month_window(now)
    with account_session(runtime_engine, owners[0]) as session:
        for moment, inputs, outputs in [
            (start, 3, 4),
            (now, None, None),
            (now, 0, 0),
            (start - timedelta(microseconds=1), 999, 999),
            (end, 999, 999),
        ]:
            session.add(
                LLMUsage(
                    user_id=owners[0],
                    provider="groq",
                    outcome="ok",
                    created_at=moment,
                    input_tokens=inputs,
                    output_tokens=outputs,
                    elapsed_ms=10,
                )
            )
    with account_session(runtime_engine, owners[1]) as session:
        session.add(
            LLMUsage(
                user_id=owners[1],
                provider="groq",
                outcome="error",
                created_at=now,
                input_tokens=999,
                output_tokens=999,
                elapsed_ms=999,
            )
        )
    result = llm_consumption(runtime_engine, owners[0], now)
    assert result.attempts == 3 and result.elapsed_ms == 30
    assert result.input_tokens == 3 and result.output_tokens == 4
    assert result.unknown_input_attempts == result.unknown_output_attempts == 1
    assert result.period_start == start and result.period_end == end
    assert llm_consumption(runtime_engine, owners[1], now).input_tokens == 999
    with account_session(runtime_engine, owners[0]) as session:
        session.execute(delete(LLMUsage).where(LLMUsage.user_id == owners[0]))
    empty = llm_consumption(runtime_engine, owners[0], now)
    assert empty.attempts == empty.elapsed_ms == empty.unknown_input_attempts == 0
    assert empty.input_tokens is None and empty.output_tokens is None
    with account_session(runtime_engine, owners[0]) as session:
        session.add(
            LLMUsage(
                user_id=owners[0], provider="groq", outcome="error", created_at=now, elapsed_ms=1
            )
        )
    unknown = llm_consumption(runtime_engine, owners[0], now)
    assert (
        unknown.attempts == unknown.unknown_input_attempts == unknown.unknown_output_attempts == 1
    )
    assert unknown.input_tokens is None and unknown.output_tokens is None
    with account_session(runtime_engine, owners[0]) as session:
        user = session.get(User, owners[0])
        user.deletion_requested_at = now
        session.add(user)
    with pytest.raises(LLMUnavailable):
        llm_consumption(runtime_engine, owners[0], now)
