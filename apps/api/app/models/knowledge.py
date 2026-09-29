from typing import ClassVar
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Column, Computed, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, SQLModel


class KnowledgeChunk(SQLModel, table=True):
    __tablename__: ClassVar[str] = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("slug", "position"),
        CheckConstraint("position >= 0", name="position"),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest"),
        Index("ix_knowledge_search", "search_vector", postgresql_using="gin"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    slug: str = Field(max_length=160)
    position: int = Field(ge=0)
    section: str = Field(max_length=200)
    content: str = Field(sa_type=Text)
    content_digest: str = Field(max_length=64)
    embedding: list[float] = Field(sa_column=Column(Vector(384), nullable=False))
    embedding_model: str = Field(max_length=120)
    search_vector: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR, Computed("to_tsvector('portuguese'::regconfig, content)", persisted=True)
        ),
    )
