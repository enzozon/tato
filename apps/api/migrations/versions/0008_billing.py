"""Cobrança sandbox e métricas técnicas, schema aprovado em 07/10/2026."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind in [
        ("billing_provider", sa.String(16)),
        ("external_id", sa.String(255)),
        ("external_customer_id", sa.String(255)),
        ("valid_until", sa.DateTime(timezone=True)),
    ]:
        op.add_column("subscriptions", sa.Column(name, kind))
    op.create_check_constraint(
        "provider", "subscriptions", "billing_provider IN ('stripe', 'abacatepay')"
    )
    op.create_check_constraint(
        "billing_link",
        "subscriptions",
        "billing_provider IS NOT NULL OR "
        "(external_id IS NULL AND external_customer_id IS NULL AND valid_until IS NULL)",
    )
    for name in ["external_id", "external_customer_id"]:
        op.create_unique_constraint(
            f"uq_subscriptions_billing_provider_{name}", "subscriptions", ["billing_provider", name]
        )
    columns = {
        "billing_checkouts": [
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column("request_id", sa.Uuid(), nullable=False),
            sa.Column("external_id", sa.String(255)),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("user_id", "request_id"),
            sa.UniqueConstraint("provider", "external_id"),
            sa.CheckConstraint("provider IN ('stripe', 'abacatepay')", name="provider"),
            sa.CheckConstraint("status IN ('pending', 'paid', 'canceled')", name="status"),
            sa.CheckConstraint("amount_cents > 0", name="amount"),
        ],
        "billing_events": [
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column("event_id", sa.String(255), nullable=False),
            sa.UniqueConstraint("provider", "event_id"),
            sa.CheckConstraint("provider IN ('stripe', 'abacatepay')", name="provider"),
        ],
        "llm_usage": [
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column("outcome", sa.String(16), nullable=False),
            sa.Column("input_tokens", sa.BigInteger()),
            sa.Column("output_tokens", sa.BigInteger()),
            sa.Column("elapsed_ms", sa.BigInteger(), nullable=False),
            sa.CheckConstraint("provider IN ('groq', 'gemini', 'openrouter')", name="provider"),
            sa.CheckConstraint(
                "outcome IN ('ok', 'invalid', 'error', 'policy', 'circuit_open')", name="outcome"
            ),
            sa.CheckConstraint("input_tokens >= 0", name="input_tokens"),
            sa.CheckConstraint("output_tokens >= 0", name="output_tokens"),
            sa.CheckConstraint("elapsed_ms >= 0", name="elapsed_ms"),
        ],
    }
    condition = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    for table, fields in columns.items():
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            *fields,
        )
        op.create_index(f"ix_{table}_user_created", table, ["user_id", "created_at"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_access ON {table} TO tato_app "
            f"USING ({condition}) WITH CHECK ({condition})"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO tato_app")


def downgrade() -> None:
    for table in ["llm_usage", "billing_events", "billing_checkouts"]:
        op.drop_table(table)
    for name in ["external_id", "external_customer_id"]:
        op.drop_constraint(
            f"uq_subscriptions_billing_provider_{name}", "subscriptions", type_="unique"
        )
    for name in ["billing_link", "provider"]:
        op.drop_constraint(op.f(f"ck_subscriptions_{name}"), "subscriptions", type_="check")
    for name in ["valid_until", "external_customer_id", "external_id", "billing_provider"]:
        op.drop_column("subscriptions", name)
