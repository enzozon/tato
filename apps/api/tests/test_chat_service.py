from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import chat_service as service
from app.chat_contracts import ChatInput, ChatReply
from app.chat_history import Reservation
from app.chat_intent import Analytical, Conceptual, Conversation, Decision, Entry
from app.chat_tools import ExpenseResult


@pytest.fixture
def context(monkeypatch):
    session = Mock()

    @contextmanager
    def scope(*args):
        yield session

    monkeypatch.setattr(service, "account_session", scope)
    monkeypatch.setattr(service, "require_active", lambda *a: None)
    monkeypatch.setattr(service, "authorize", lambda *a, **kw: None)
    monkeypatch.setattr(service, "load_key", lambda *a: b"x" * 32)
    monkeypatch.setattr(service, "recent_history", lambda *a: [])
    return session


def test_reply_paths(context, monkeypatch):
    owner, turn = uuid4(), uuid4()
    data = ChatInput(request_id=uuid4(), question="sintético", account_id=uuid4())
    choices = [
        Conversation(clarify=False),
        Conceptual(),
        Entry(
            amount_cents=4200, kind="expense", booked_on=date(2026, 1, 1), description="sintético"
        ),
        Analytical(start=date(2026, 1, 1), end=date(2026, 2, 1)),
    ]
    monkeypatch.setattr(service, "conceptual_sources", lambda *a: [])
    context.get.return_value = Mock(user_id=owner, deletion_requested_at=None)
    monkeypatch.setattr(
        service, "run_expense_query", lambda s, o, q: ExpenseResult(source=q, amount_cents=4200)
    )
    for choice in choices:
        monkeypatch.setattr(
            service, "classify", lambda *a, selected=choice: Decision(choice=selected)
        )
        reply = service.build_reply(None, owner, data, turn, b"x" * 32)
        assert reply.intent == choice.intent
        if isinstance(choice, Entry):
            assert reply.draft == choice and reply.transaction_id is None
        if isinstance(choice, Analytical):
            assert "42,00" in reply.message
    context.exec.return_value.all.return_value = []
    monkeypatch.setattr(
        service,
        "classify",
        lambda *a: Decision(choice=choices[-1].model_copy(update={"category": "ausente"})),
    )
    assert service.build_reply(None, owner, data, turn, b"x" * 32).expense is None


def test_response_finalizes_before_return_and_recovers_retries(context, monkeypatch):
    owner, turn = uuid4(), uuid4()
    data = ChatInput(request_id=uuid4(), question="oi")
    reply = ChatReply(turn_id=turn, intent="conversation", message="olá")
    finish = Mock()
    monkeypatch.setattr(service, "finish_turn", finish)
    monkeypatch.setattr(service, "build_reply", lambda *a: reply)
    monkeypatch.setattr(service, "reserve_turn", lambda *a: Reservation(turn, "pending", True))
    assert service.respond(None, owner, data) == reply
    assert finish.call_args.args[3] == reply.model_dump_json()
    finish.reset_mock()
    monkeypatch.setattr(
        service,
        "reserve_turn",
        lambda *a: Reservation(turn, "completed", False, reply.model_dump_json()),
    )
    assert service.respond(None, owner, data) == reply
    finish.assert_not_called()


def test_failure_is_finalized_without_private_error(context, monkeypatch):
    turn = uuid4()
    monkeypatch.setattr(service, "reserve_turn", lambda *a: Reservation(turn, "pending", True))
    monkeypatch.setattr(service, "build_reply", Mock(side_effect=ValueError("segredo")))
    finish = Mock()
    monkeypatch.setattr(service, "finish_turn", finish)
    with pytest.raises(ValueError):
        service.respond(None, uuid4(), ChatInput(request_id=uuid4(), question="oi"))
    assert finish.call_args.args[3] is None
