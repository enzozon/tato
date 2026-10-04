from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app.account_service import account_session
from app.chat_history import finish_turn, recent_history, reserve_turn
from app.crypto import encrypt_text
from app.llm import LLMUnavailable
from app.models import ChatTurn, User

pytestmark = pytest.mark.integration
KEY = b"x" * 32


def test_encrypted_history_retry_conflict_and_deletion(admin_engine, runtime_engine, owners):
    owner, other = owners
    request_id = uuid4()
    first = reserve_turn(runtime_engine, owner, request_id, "pergunta sintética", KEY)
    assert first.created and first.status == "pending"
    retry = reserve_turn(runtime_engine, owner, request_id, "pergunta sintética", KEY)
    assert not retry.created and retry.turn_id == first.turn_id
    with pytest.raises(HTTPException) as error:
        reserve_turn(runtime_engine, owner, request_id, "outra pergunta", KEY)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException), account_session(runtime_engine, other) as session:
        finish_turn(session, other, first.turn_id, "resposta", KEY)
    with account_session(runtime_engine, owner) as session:
        finish_turn(session, owner, first.turn_id, "resposta sintética", KEY)
    retry = reserve_turn(runtime_engine, owner, request_id, "pergunta sintética", KEY)
    assert retry.status == "completed" and retry.response == "resposta sintética"
    assert "sintética" not in repr(retry)
    assert recent_history(runtime_engine, owner, KEY) == [
        ("pergunta sintética", "resposta sintética")
    ]
    assert recent_history(runtime_engine, other, KEY) == []
    with Session(admin_engine) as session:
        row = session.get(ChatTurn, first.turn_id)
        assert b"pergunta" not in row.request_ciphertext
        assert b"resposta" not in row.response_ciphertext
    with admin_engine.begin() as connection:
        connection.execute(
            update(User).where(User.id == owner).values(deletion_requested_at=datetime.now(UTC))
        )
    with pytest.raises(LLMUnavailable):
        recent_history(runtime_engine, owner, KEY)


@pytest.mark.parametrize("same_request", [True, False])
def test_monthly_quota_is_atomic_and_retries_do_not_charge(
    admin_engine, runtime_engine, owners, same_request
):
    owner = owners[0]
    now = datetime.now(UTC)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with Session(admin_engine) as session, session.begin():
        for index in range(200):
            session.add(
                ChatTurn(
                    user_id=owner,
                    request_id=uuid4(),
                    request_ciphertext=b"cifrado",
                    created_at=month - timedelta(seconds=1) if index == 199 else month,
                    status="failed",
                    completed_at=now,
                )
            )
    request_id = uuid4()

    def reserve(identifier):
        try:
            return reserve_turn(runtime_engine, owner, identifier, "sintético", KEY)
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, [request_id, request_id if same_request else uuid4()]))
    accepted = [result for result in results if not isinstance(result, int)]
    assert sum(result.created for result in accepted) == 1
    if same_request:
        assert accepted[0].turn_id == accepted[1].turn_id
    else:
        assert results.count(403) == 1
    assert reserve(uuid4()) == 403
    with account_session(runtime_engine, owner) as session:
        finish_turn(session, owner, accepted[0].turn_id, None, KEY)
    if same_request:
        assert reserve(request_id).status == "failed"
    assert reserve(uuid4()) == 403


def test_stale_pending_cannot_finish_after_retry(admin_engine, runtime_engine, owners):
    owner = owners[0]
    request_id = uuid4()
    turn = reserve_turn(runtime_engine, owner, request_id, "sintético", KEY)
    with admin_engine.begin() as connection:
        connection.execute(
            update(ChatTurn)
            .where(ChatTurn.id == turn.turn_id)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=6))
        )
    retry = reserve_turn(runtime_engine, owner, request_id, "sintético", KEY)
    assert retry.status == "failed" and not retry.created
    with pytest.raises(HTTPException), account_session(runtime_engine, owner) as session:
        finish_turn(session, owner, turn.turn_id, "tarde demais", KEY)


def test_history_has_turn_and_text_limits(admin_engine, runtime_engine, owners):
    owner = owners[0]
    with Session(admin_engine) as session, session.begin():
        for index in range(12):
            session.add(
                ChatTurn(
                    user_id=owner,
                    request_id=uuid4(),
                    status="completed",
                    created_at=datetime.now(UTC) + timedelta(seconds=index),
                    completed_at=datetime.now(UTC),
                    request_ciphertext=encrypt_text(str(index), KEY, owner, "chat_request"),
                    response_ciphertext=encrypt_text("r", KEY, owner, "chat_response"),
                )
            )
    assert [pair[0] for pair in recent_history(runtime_engine, owner, KEY)] == list(
        map(str, range(2, 12))
    )
    with Session(admin_engine) as session, session.begin():
        last = session.exec(
            select(ChatTurn).where(ChatTurn.user_id == owner).order_by(ChatTurn.created_at.desc())
        ).first()
        last.response_ciphertext = encrypt_text("r" * 11999, KEY, owner, "chat_response")
        session.add(last)
    assert recent_history(runtime_engine, owner, KEY) == []
