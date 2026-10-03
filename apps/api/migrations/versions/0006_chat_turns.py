"""Histórico cifrado e identidade de pedidos aprovados no checkpoint da etapa 7."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_turns",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("response_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "request_id"),
        sa.CheckConstraint(
            "(status = 'pending' AND response_ciphertext IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND response_ciphertext IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'failed' AND response_ciphertext IS NULL AND completed_at IS NOT NULL)",
            name="state",
        ),
    )
    op.create_index("ix_chat_turns_user_created", "chat_turns", ["user_id", "created_at", "id"])
    condition = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE chat_turns ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_turns FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_access ON chat_turns TO tato_app "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON chat_turns TO tato_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON chat_turns FROM tato_app")
    op.drop_table("chat_turns")
