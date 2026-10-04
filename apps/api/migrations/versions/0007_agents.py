"""Configuração e entrega dos agentes, schema aprovado em 04/10/2026."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_goals_user_id_id", "goals", ["user_id", "id"])
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        sa.ForeignKeyConstraint(["user_id", "goal_id"], ["goals.user_id", "goals.id"]),
        sa.UniqueConstraint("user_id", "kind"),
        sa.CheckConstraint(
            "kind IN ('subscription_watch', 'anomaly', 'runway', 'goal')", name="kind"
        ),
        sa.CheckConstraint("(kind = 'goal') = (goal_id IS NOT NULL)", name="goal_link"),
    )
    condition = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    op.execute("ALTER TABLE agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agents FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_access ON agents TO tato_app "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agents TO tato_app")
    op.add_column(
        "insights", sa.Column("email_status", sa.String(10), nullable=False, server_default="off")
    )
    op.add_column(
        "insights", sa.Column("email_attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("insights", sa.Column("email_last_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("insights", sa.Column("email_sent_at", sa.DateTime(timezone=True)))
    op.alter_column("insights", "email_status", server_default=None)
    op.alter_column("insights", "email_attempts", server_default=None)
    op.create_check_constraint(
        "email_status", "insights", "email_status IN ('off', 'pending', 'sent')"
    )
    op.create_check_constraint("email_attempts", "insights", "email_attempts >= 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_insights_email_attempts"), "insights", type_="check")
    op.drop_constraint(op.f("ck_insights_email_status"), "insights", type_="check")
    for column in ["email_sent_at", "email_last_attempt_at", "email_attempts", "email_status"]:
        op.drop_column("insights", column)
    op.drop_table("agents")
    op.drop_constraint("uq_goals_user_id_id", "goals", type_="unique")
