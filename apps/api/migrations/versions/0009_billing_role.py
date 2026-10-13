"""Isola a escrita de cobrança em papel restrito, aprovado pelo proprietário."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

TABLES = ("subscriptions", "billing_checkouts", "billing_events")
TENANT = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'tato_billing') THEN
                CREATE ROLE tato_billing NOLOGIN;
            END IF;
        END; $$
    """)
    op.execute(
        "ALTER ROLE tato_billing NOSUPERUSER NOBYPASSRLS NOCREATEDB "
        "NOCREATEROLE NOREPLICATION NOINHERIT"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO tato_billing")
    op.execute("GRANT SELECT ON users TO tato_billing")
    op.execute(
        "CREATE POLICY billing_read ON users FOR SELECT TO tato_billing "
        "USING (id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
    )
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO tato_billing")
        op.execute(
            f"CREATE POLICY billing_access ON {table} TO tato_billing "
            f"USING ({TENANT}) WITH CHECK ({TENANT})"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY billing_access ON {table}")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM tato_billing")
    op.execute("DROP POLICY billing_read ON users")
    op.execute("REVOKE SELECT ON users FROM tato_billing")
    op.execute("REVOKE USAGE ON SCHEMA public FROM tato_billing")
    # O papel pode ter sessões ativas ou dependências em outro banco do cluster.
