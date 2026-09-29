"""Base pública e identificação do encoder aprovadas no checkpoint da etapa 6."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("embedding_model", sa.String(120), nullable=True))
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR,
            sa.Computed("to_tsvector('portuguese'::regconfig, content)", persisted=True),
        ),
        sa.UniqueConstraint("slug", "position"),
        sa.CheckConstraint("position >= 0", name="position"),
        sa.CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest"),
    )
    op.create_index(
        "ix_knowledge_search", "knowledge_chunks", ["search_vector"], postgresql_using="gin"
    )
    op.execute("GRANT SELECT ON knowledge_chunks TO tato_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON knowledge_chunks FROM tato_app")
    op.drop_index("ix_knowledge_search", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_column("chunks", "embedding_model")
