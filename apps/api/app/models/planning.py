from datetime import date, datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
)
from sqlmodel import Field

from app.models.base import TenantRecord


class Rule(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "rules"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "category_id"], ["categories.user_id", "categories.id"]),
        Index("ix_rules_user_category", "user_id", "category_id"),
        CheckConstraint("priority >= 0", name="priority"),
    )
    pattern_ciphertext: bytes
    category_id: UUID
    priority: int = Field(default=0, ge=0)
    enabled: bool = True


class Goal(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "goals"
    __table_args__ = (
        Index("ix_goals_user", "user_id"),
        UniqueConstraint("user_id", "id"),
        CheckConstraint("target_cents > 0", name="target"),
    )
    description_ciphertext: bytes
    target_cents: int = Field(gt=0, sa_type=BigInteger)
    due_on: date | None = None


class Insight(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "insights"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key"),
        CheckConstraint("email_status IN ('off', 'pending', 'sent')", name="email_status"),
        CheckConstraint("email_attempts >= 0", name="email_attempts"),
        CheckConstraint(
            "agent_kind IN ('subscription_watch', 'anomaly', 'runway', 'goal')", name="agent_kind"
        ),
    )
    agent_kind: str = Field(max_length=32)
    content_ciphertext: bytes
    event_key: str = Field(min_length=1, max_length=128)
    read_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    email_status: str = Field(default="off", max_length=10)
    email_attempts: int = Field(default=0)
    email_last_attempt_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    email_sent_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class Subscription(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("plan IN ('free', 'pro')", name="plan"),
        CheckConstraint("status IN ('active', 'past_due', 'canceled')", name="status"),
    )
    plan: str = Field(default="free", max_length=10)
    status: str = Field(default="active", max_length=16)
