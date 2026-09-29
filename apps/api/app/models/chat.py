from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantRecord


class ChatTurn(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "chat_turns"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id"),
        Index("ix_chat_turns_user_created", "user_id", "created_at", "id"),
        CheckConstraint(
            "(status = 'pending' AND response_ciphertext IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND response_ciphertext IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'failed' AND response_ciphertext IS NULL AND completed_at IS NOT NULL)",
            name="state",
        ),
    )
    request_id: UUID
    request_ciphertext: bytes
    response_ciphertext: bytes | None = None
    status: str = Field(default="pending", max_length=10)
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
