from typing import ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantRecord


class Agent(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "agents"
    __table_args__ = (
        UniqueConstraint("user_id", "kind"),
        ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        ForeignKeyConstraint(["user_id", "goal_id"], ["goals.user_id", "goals.id"]),
        CheckConstraint("kind IN ('subscription_watch', 'anomaly', 'runway', 'goal')", name="kind"),
        CheckConstraint("(kind = 'goal') = (goal_id IS NOT NULL)", name="goal_link"),
    )
    kind: str = Field(max_length=32)
    enabled: bool = True
    account_id: UUID
    goal_id: UUID | None = None
    email_enabled: bool = False
