from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlmodel import col, select

from app.account_service import account_session
from app.agent_config import GoalInput
from app.agent_rules import Signal
from app.crypto import decrypt_text, load_key
from app.llm_service import require_active
from app.models import Goal, Insight


class InsightView(BaseModel):
    id: UUID
    created_at: datetime
    read_at: datetime | None
    signal: Signal


class GoalView(GoalInput):
    id: UUID


def insights(engine: Engine, owner: UUID, limit: int) -> list[InsightView]:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        rows = session.exec(
            select(Insight)
            .where(Insight.user_id == owner)
            .order_by(col(Insight.created_at).desc(), col(Insight.id).desc())
            .limit(limit)
        ).all()
        return [
            InsightView(
                id=row.id,
                created_at=row.created_at,
                read_at=row.read_at,
                signal=Signal.model_validate_json(
                    decrypt_text(row.content_ciphertext, key, owner, "insight")
                ),
            )
            for row in rows
        ]


def mark_read(engine: Engine, owner: UUID, insight_id: UUID) -> None:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        row = session.get(Insight, insight_id)
        if row is None or row.user_id != owner:
            raise HTTPException(404, "Aviso não encontrado.")
        if row.read_at is None:
            row.read_at = datetime.now(UTC)
            session.add(row)


def goals(engine: Engine, owner: UUID) -> list[GoalView]:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        rows = session.exec(
            select(Goal)
            .where(Goal.user_id == owner)
            .order_by(col(Goal.created_at), col(Goal.id))
            .limit(100)
        ).all()
        return [
            GoalView(
                id=row.id,
                target_cents=row.target_cents,
                due_on=row.due_on,
                description=decrypt_text(row.description_ciphertext, key, owner, "goal"),
            )
            for row in rows
        ]
