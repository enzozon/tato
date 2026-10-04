from datetime import date
from typing import Self
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine
from sqlmodel import col, select

from app.account_service import account_session
from app.agent_rules import AgentKind
from app.crypto import encrypt_text, load_key
from app.import_service import active_account
from app.llm_service import require_active
from app.models import Account, Agent, Goal
from app.plans import require_capacity, user_plan
from app.rate_limit import check_rate


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: UUID
    goal_id: UUID | None = None
    enabled: bool = Field(default=True, strict=True)
    email_enabled: bool = Field(default=False, strict=True)


class AgentView(AgentInput):
    id: UUID
    kind: AgentKind


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=500, repr=False)
    target_cents: int = Field(gt=0, lt=2**63, strict=True)
    due_on: date | None = None

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.description.strip():
            raise ValueError("Descreva a meta.")
        return self


def configure(engine: Engine, owner: UUID, kind: AgentKind, data: AgentInput) -> AgentView:
    with account_session(engine, owner) as session:
        active_account(session, owner, data.account_id)
        plan = user_plan(session, owner)
        check_rate(owner, plan.requests_per_minute)
        account = session.get(Account, data.account_id)
        if kind in {"goal", "runway"} and account is not None and account.kind == "credit_card":
            raise HTTPException(422, "Meta e fôlego exigem uma conta, não cartão de crédito.")
        if (kind == "goal") != (data.goal_id is not None):
            raise HTTPException(422, "Somente o agente Meta exige goal_id.")
        if data.goal_id is not None:
            goal = session.get(Goal, data.goal_id)
            if goal is None or goal.user_id != owner:
                raise HTTPException(404, "Meta não encontrada.")
        rows = session.exec(select(Agent).where(Agent.user_id == owner)).all()
        current = next((row for row in rows if row.kind == kind), None)
        if data.enabled:
            require_capacity(plan, "agents", sum(row.enabled for row in rows if row.kind != kind))
        if current is None:
            current = Agent(user_id=owner, kind=kind, **data.model_dump())
        else:
            for name, value in data.model_dump().items():
                setattr(current, name, value)
        session.add(current)
        session.flush()
        result = AgentView(id=current.id, kind=kind, **data.model_dump())
    return result


def list_agents(engine: Engine, owner: UUID) -> list[AgentView]:
    with account_session(engine, owner) as session:
        require_active(session, owner)
        return [
            AgentView.model_validate({key: getattr(row, key) for key in AgentView.model_fields})
            for row in session.exec(
                select(Agent)
                .where(Agent.user_id == owner)
                .order_by(col(Agent.created_at), col(Agent.id))
            ).all()
        ]


def create_goal(engine: Engine, owner: UUID, data: GoalInput) -> UUID:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        ids = session.exec(select(Goal.id).where(Goal.user_id == owner).limit(100)).all()
        if len(ids) >= 100:
            raise HTTPException(409, "Limite técnico de metas atingido.")
        goal = Goal(
            user_id=owner,
            description_ciphertext=encrypt_text(data.description, key, owner, "goal"),
            target_cents=data.target_cents,
            due_on=data.due_on,
        )
        session.add(goal)
        session.flush()
        result = goal.id
    return result
