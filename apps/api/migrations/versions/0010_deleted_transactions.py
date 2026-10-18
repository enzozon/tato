"""Preserva identidades removidas, schema aprovado em 18/10/2026."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_transactions",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        sa.UniqueConstraint("user_id", "account_id", "dedup_key"),
        sa.CheckConstraint("dedup_key ~ '^[0-9a-f]{64}$'", name="dedup_key"),
    )
    condition = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE deleted_transactions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE deleted_transactions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_access ON deleted_transactions TO tato_app "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON deleted_transactions TO tato_app")


def downgrade() -> None:
    op.drop_table("deleted_transactions")
