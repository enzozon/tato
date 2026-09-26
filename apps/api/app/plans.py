from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.models import Subscription


class Plan(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: Literal["free", "pro"]
    agents: int
    messages_per_month: int | None
    import_sources: int | None
    reports: bool
    requests_per_minute: int


FREE = Plan(
    name="free",
    agents=1,
    messages_per_month=200,
    import_sources=1,
    reports=False,
    requests_per_minute=60,
)
PRO = Plan(
    name="pro",
    agents=3,
    messages_per_month=None,
    import_sources=None,
    reports=True,
    requests_per_minute=300,
)


def user_plan(session: Session, owner: UUID) -> Plan:
    subscription = session.exec(select(Subscription).where(Subscription.user_id == owner)).first()
    if subscription and subscription.plan == "pro" and subscription.status == "active":
        return PRO
    return FREE


def require_capacity(
    plan: Plan, feature: Literal["agents", "messages_per_month", "import_sources"], used: int
) -> None:
    """Recebe contagem autoritativa do backend, nunca do corpo da requisição."""
    if used < 0:
        raise ValueError("Contagem não pode ser negativa.")
    limit = getattr(plan, feature)
    if limit is not None and used >= limit:
        raise HTTPException(403, "Limite do plano atingido.")


def require_reports(plan: Plan) -> None:
    if not plan.reports:
        raise HTTPException(403, "Relatórios exigem plano Pro ativo.")
