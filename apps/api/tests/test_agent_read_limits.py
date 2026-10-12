from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import agent_config, insight_service
from app.llm import LLMUnavailable
from app.models import User
from app.plans import FREE, PRO


@pytest.mark.parametrize("plan", [FREE, PRO], ids=["free", "pro"])
@pytest.mark.parametrize(
    ("module", "function", "args"),
    [
        (agent_config, "list_agents", ()),
        (insight_service, "insights", (50,)),
        (insight_service, "goals", ()),
        (insight_service, "mark_read", (uuid4(),)),
    ],
)
def test_read_limit_blocks_queries_and_mutations(monkeypatch, plan, module, function, args):
    owner, engine = uuid4(), Mock()
    session = Mock()
    session.get.return_value = User(id=owner)

    @contextmanager
    def transaction(actual_engine, actual_owner):
        assert (actual_engine, actual_owner) == (engine, owner)
        yield session

    limiter = Mock(side_effect=HTTPException(429, "Muitas requisições."))
    current_plan = Mock(return_value=plan)
    monkeypatch.setattr(module, "account_session", transaction)
    monkeypatch.setattr(module, "user_plan", current_plan)
    monkeypatch.setattr(module, "check_rate", limiter)
    monkeypatch.setattr(module, "load_key", lambda name: b"k" * 32)
    with pytest.raises(HTTPException) as error:
        getattr(module, function)(engine, owner, *args)
    assert error.value.status_code == 429
    current_plan.assert_called_once_with(session, owner)
    limiter.assert_called_once_with(owner, plan.requests_per_minute)
    session.get.assert_called_once_with(User, owner)
    session.exec.assert_not_called()
    session.add.assert_not_called()

    # Exclusão pendente continua sendo verificada antes do limite e da leitura.
    session.get.return_value = User(id=owner, deletion_requested_at=datetime.now(UTC))
    limiter.reset_mock()
    with pytest.raises(LLMUnavailable):
        getattr(module, function)(engine, owner, *args)
    limiter.assert_not_called()
