from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantRecord


class BillingCheckout(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "billing_checkouts"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id"),
        UniqueConstraint("provider", "external_id"),
        Index("ix_billing_checkouts_user_created", "user_id", "created_at"),
        CheckConstraint("provider IN ('stripe', 'abacatepay')", name="provider"),
        CheckConstraint("status IN ('pending', 'paid', 'canceled')", name="status"),
        CheckConstraint("amount_cents > 0", name="amount"),
    )
    provider: str = Field(max_length=16)
    request_id: UUID
    external_id: str | None = Field(default=None, max_length=255)
    amount_cents: int = Field(gt=0, sa_type=BigInteger)
    status: str = Field(default="pending", max_length=16)
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class BillingEvent(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id"),
        Index("ix_billing_events_user_created", "user_id", "created_at"),
        CheckConstraint("provider IN ('stripe', 'abacatepay')", name="provider"),
    )
    provider: str = Field(max_length=16)
    event_id: str = Field(min_length=1, max_length=255)


class LLMUsage(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        CheckConstraint("provider IN ('groq', 'gemini', 'openrouter')", name="provider"),
        CheckConstraint(
            "outcome IN ('ok', 'invalid', 'error', 'policy', 'circuit_open')", name="outcome"
        ),
        CheckConstraint("input_tokens >= 0", name="input_tokens"),
        CheckConstraint("output_tokens >= 0", name="output_tokens"),
        CheckConstraint("elapsed_ms >= 0", name="elapsed_ms"),
    )
    provider: str = Field(max_length=16)
    outcome: str = Field(max_length=16)
    input_tokens: int | None = Field(default=None, sa_type=BigInteger)
    output_tokens: int | None = Field(default=None, sa_type=BigInteger)
    elapsed_ms: int = Field(sa_type=BigInteger)
