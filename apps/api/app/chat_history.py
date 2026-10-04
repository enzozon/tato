from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.account_service import account_session
from app.crypto import decrypt_text, encrypt_text
from app.llm_service import require_active
from app.models import ChatTurn
from app.plans import require_capacity, user_plan


@dataclass(frozen=True)
class Reservation:
    turn_id: UUID
    status: str
    created: bool
    response: str | None = field(default=None, repr=False)


def reserve_turn(
    engine: Engine, owner: UUID, request_id: UUID, request: str, key: bytes
) -> Reservation:
    if not request.strip() or len(request) > 8000:
        raise ValueError("Pedido deve conter entre 1 e 8000 caracteres.")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        now = datetime.now(UTC)
        turn = session.exec(
            select(ChatTurn).where(ChatTurn.user_id == owner, ChatTurn.request_id == request_id)
        ).first()
        if turn is not None:
            if decrypt_text(turn.request_ciphertext, key, owner, "chat_request") != request:
                raise HTTPException(409, "Identificador já usado para outro pedido.")
            if turn.status == "pending" and turn.created_at <= now - timedelta(minutes=5):
                turn.status, turn.completed_at = "failed", now
                session.add(turn)
            response = (
                decrypt_text(turn.response_ciphertext, key, owner, "chat_response")
                if turn.response_ciphertext is not None
                else None
            )
            return Reservation(turn.id, turn.status, False, response)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        used = session.exec(
            select(func.count())
            .select_from(ChatTurn)
            .where(
                ChatTurn.user_id == owner, ChatTurn.created_at >= start, ChatTurn.created_at < end
            )
        ).one()
        require_capacity(user_plan(session, owner), "messages_per_month", used)
        turn = ChatTurn(
            user_id=owner,
            request_id=request_id,
            created_at=now,
            request_ciphertext=encrypt_text(request, key, owner, "chat_request"),
        )
        session.add(turn)
        session.flush()
        return Reservation(turn.id, turn.status, True)


def finish_turn(
    session: Session, owner: UUID, turn_id: UUID, response: str | None, key: bytes
) -> None:
    """Usar dentro de account_session, na mesma transação de eventual lançamento."""
    require_active(session, owner)
    turn = session.exec(
        select(ChatTurn).where(ChatTurn.user_id == owner, ChatTurn.id == turn_id)
    ).first()
    if turn is None or turn.status != "pending":
        raise HTTPException(409, "Pedido ausente ou já finalizado.")
    if response is not None and (not response.strip() or len(response) > 16000):
        raise ValueError("Resposta deve conter entre 1 e 16000 caracteres.")
    turn.response_ciphertext = (
        encrypt_text(response, key, owner, "chat_response") if response is not None else None
    )
    turn.status = "completed" if response is not None else "failed"
    turn.completed_at = datetime.now(UTC)
    session.add(turn)


def recent_history(engine: Engine, owner: UUID, key: bytes) -> list[tuple[str, str]]:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        turns = session.exec(
            select(ChatTurn)
            .where(ChatTurn.user_id == owner, ChatTurn.status == "completed")
            .order_by(col(ChatTurn.created_at).desc(), col(ChatTurn.id).desc())
            .limit(10)
        ).all()
        history: list[tuple[str, str]] = []
        remaining = 12000
        for turn in turns:
            question = decrypt_text(turn.request_ciphertext, key, owner, "chat_request")
            assert turn.response_ciphertext is not None
            answer = decrypt_text(turn.response_ciphertext, key, owner, "chat_response")
            if len(question) + len(answer) > remaining:
                break
            remaining -= len(question) + len(answer)
            history.append((question, answer))
        return list(reversed(history))
