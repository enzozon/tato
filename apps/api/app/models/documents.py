from typing import ClassVar
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Column, ForeignKeyConstraint, Index, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantRecord


class Document(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "documents"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        Index("ix_documents_user_account", "user_id", "account_id"),
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "digest"),
        CheckConstraint("kind IN ('csv', 'ofx', 'pdf', 'note', 'summary')", name="kind"),
        CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="digest"),
    )
    name_ciphertext: bytes
    account_id: UUID | None = None
    content_ciphertext: bytes
    kind: str = Field(max_length=10)
    digest: str = Field(max_length=64)


class Chunk(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "document_id"], ["documents.user_id", "documents.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("user_id", "document_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )
    document_id: UUID
    position: int = Field(ge=0)
    content_ciphertext: bytes
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(384)))
