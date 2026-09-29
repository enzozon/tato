from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlmodel import Session, select

from app.database import tenant_session
from app.models import ChatTurn, User

pytestmark = pytest.mark.integration


def test_chat_rls_identity_and_cascade(admin_engine, runtime_engine, owners):
    owner, other = owners
    request_id = uuid4()
    identifiers = []
    for user in owners:
        with tenant_session(runtime_engine, user) as session:
            turn = ChatTurn(user_id=user, request_id=request_id, request_ciphertext=b"cifrado")
            session.add(turn)
            session.flush()
            identifiers.append(turn.id)
    with tenant_session(runtime_engine, owner) as session:
        assert [row.id for row in session.exec(select(ChatTurn))] == [identifiers[0]]
        assert session.get(ChatTurn, identifiers[1]) is None
    with pytest.raises(IntegrityError), tenant_session(runtime_engine, owner) as session:
        session.add(ChatTurn(user_id=owner, request_id=request_id, request_ciphertext=b"cifrado"))
        session.flush()
    with pytest.raises(ProgrammingError), tenant_session(runtime_engine, owner) as session:
        session.add(ChatTurn(user_id=other, request_id=uuid4(), request_ciphertext=b"cifrado"))
        session.flush()
    with admin_engine.begin() as connection:
        connection.execute(delete(User).where(User.id == owner))
    with Session(admin_engine) as session:
        assert session.get(ChatTurn, identifiers[0]) is None
        assert session.get(ChatTurn, identifiers[1]) is not None


def test_chat_state_constraint(admin_engine, owners):
    turn = ChatTurn(user_id=owners[0], request_id=uuid4(), request_ciphertext=b"cifrado")
    with Session(admin_engine) as session, session.begin():
        session.add(turn)
        session.flush()
        identifier = turn.id
    for values in [
        {"status": "inventado"},
        {"status": "completed"},
        {"status": "failed"},
        {"response_ciphertext": b"cifrado"},
        {"completed_at": datetime.now(UTC)},
    ]:
        with pytest.raises(IntegrityError) as error, admin_engine.begin() as connection:
            connection.execute(update(ChatTurn).where(ChatTurn.id == identifier).values(**values))
        assert error.value.orig.sqlstate == "23514"
    for status, response in [("completed", b"cifrado"), ("failed", None)]:
        with admin_engine.begin() as connection:
            connection.execute(
                update(ChatTurn)
                .where(ChatTurn.id == identifier)
                .values(status=status, response_ciphertext=response, completed_at=datetime.now(UTC))
            )
