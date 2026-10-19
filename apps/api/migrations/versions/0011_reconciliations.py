"""Vincula movimentações próprias, schema aprovado em 18/10/2026."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_transactions_user_id_id", "transactions", ["user_id", "id"])
    op.create_table(
        "reconciliations",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("debit_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("credit_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("debit_previous_kind", sa.String(10), nullable=False),
        sa.Column("credit_previous_kind", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "debit_transaction_id"],
            ["transactions.user_id", "transactions.id"],
            name="fk_reconciliations_debit",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "credit_transaction_id"],
            ["transactions.user_id", "transactions.id"],
            name="fk_reconciliations_credit",
        ),
        sa.UniqueConstraint("user_id", "debit_transaction_id"),
        sa.UniqueConstraint("user_id", "credit_transaction_id"),
        sa.CheckConstraint("debit_transaction_id <> credit_transaction_id", name="distinct_legs"),
        sa.CheckConstraint("kind IN ('transfer', 'card_payment')", name="kind"),
        sa.CheckConstraint("debit_previous_kind IN ('expense', 'transfer')", name="debit_kind"),
        sa.CheckConstraint("credit_previous_kind IN ('income', 'transfer')", name="credit_kind"),
    )
    condition = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE reconciliations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_access ON reconciliations TO tato_app "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON reconciliations TO tato_app")


def downgrade() -> None:
    op.drop_table("reconciliations")
    op.drop_constraint("uq_transactions_user_id_id", "transactions", type_="unique")
