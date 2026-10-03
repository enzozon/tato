from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import chat_entry as entry
from app.chat_contracts import ChatInput, ChatReply
from app.chat_intent import Entry
from app.crypto import decrypt_text, encrypt_text


def test_confirmation_validates_persists_and_replays(monkeypatch):
    owner, turn_id, account_id, transaction_id = (uuid4() for _ in range(4))
    key = b"x" * 32
    draft = Entry(
        amount_cents=4200, kind="expense", booked_on=date(2026, 1, 1), description="teste"
    )
    request = ChatInput(
        request_id=uuid4(), question="gastei 42 no teste hoje", account_id=account_id
    )
    reply = ChatReply(turn_id=turn_id, intent="entry", message="confira", draft=draft)
    turn = Mock(
        id=turn_id,
        request_ciphertext=encrypt_text(request.model_dump_json(), key, owner, "chat_request"),
        response_ciphertext=encrypt_text(reply.model_dump_json(), key, owner, "chat_response"),
    )
    session = Mock()
    session.exec.return_value.first.return_value = turn
    session.get.side_effect = [Mock(id=account_id, user_id=owner), Mock(amount_cents=-4200)]

    @contextmanager
    def scope(*args):
        yield session

    monkeypatch.setattr(entry, "account_session", scope)
    monkeypatch.setattr(entry, "require_active", lambda *a: None)
    monkeypatch.setattr(entry, "authorize", lambda *a, **k: None)
    monkeypatch.setattr(entry, "load_key", lambda *a: key)
    monkeypatch.setattr(entry, "load_rules", lambda *a: [])
    insert = Mock(return_value=transaction_id)
    monkeypatch.setattr(entry, "add_transaction", insert)
    result = entry.confirm_entry(None, owner, turn_id)
    assert result.transaction_id == transaction_id and result.draft is None
    assert insert.call_args.args[2].amount_cents == -4200
    assert entry.confirm_entry(None, owner, turn_id) == result
    insert.assert_called_once()
    saved = ChatReply.model_validate_json(
        decrypt_text(turn.response_ciphertext, key, owner, "chat_response")
    )
    assert saved == result
    session.exec.return_value.first.return_value = None
    with pytest.raises(HTTPException) as error:
        entry.confirm_entry(None, owner, uuid4())
    assert error.value.status_code == 404
