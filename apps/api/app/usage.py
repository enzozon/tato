"""Consumo pessoal autoritativo; não estima quotas das contas dos provedores."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Engine, func
from sqlmodel import col, select

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.agent_routes import handled, no_store
from app.chat_history import month_window
from app.llm_service import require_active
from app.models import Agent, ChatTurn, Document
from app.plans import user_plan
from app.rate_limit import check_rate


class Capacity(BaseModel):
    used: int = Field(ge=0)
    limit: int | None
    remaining: int | None

    @classmethod
    def measured(cls, used: int, limit: int | None) -> "Capacity":
        return cls(
            used=used, limit=limit, remaining=None if limit is None else max(0, limit - used)
        )


class Usage(BaseModel):
    plan: Literal["free", "pro"]
    period_start: datetime
    period_end: datetime
    messages: Capacity
    import_sources: Capacity
    agents: Capacity


def consumption(engine: Engine, owner: UUID, now: datetime) -> Usage:
    start, end = month_window(now)
    with account_session(engine, owner) as session:
        require_active(session, owner)
        plan = user_plan(session, owner)
        check_rate(owner, plan.requests_per_minute)
        messages = session.exec(
            select(func.count())
            .select_from(ChatTurn)
            .where(
                ChatTurn.user_id == owner, ChatTurn.created_at >= start, ChatTurn.created_at < end
            )
        ).one()
        sources = session.exec(
            select(func.count(col(Document.account_id).distinct())).where(Document.user_id == owner)
        ).one()
        agents = session.exec(
            select(func.count())
            .select_from(Agent)
            .where(Agent.user_id == owner, col(Agent.enabled).is_(True))
        ).one()
        return Usage(
            plan=plan.name,
            period_start=start,
            period_end=end,
            messages=Capacity.measured(messages, plan.messages_per_month),
            import_sources=Capacity.measured(sources, plan.import_sources),
            agents=Capacity.measured(agents, plan.agents),
        )


router = APIRouter(tags=["consumo"], dependencies=[Depends(no_store)])


@router.get("/me/usage", response_model=Usage)
def get_usage(identity: IdentityDep, engine: EngineDep) -> Usage:
    with handled():
        return consumption(engine, identity.id, datetime.now(UTC))
