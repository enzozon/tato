"""Isolamento por usuário e permissões mínimas para o papel da API."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = (
    "users",
    "accounts",
    "categories",
    "transactions",
    "rules",
    "goals",
    "documents",
    "chunks",
    "insights",
    "subscriptions",
)


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO tato_app")
    for table in TABLES:
        owner = "id" if table == "users" else "user_id"
        condition = f"{owner} = NULLIF(current_setting('app.user_id', true), '')::uuid"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_access ON {table} TO tato_app "
            f"USING ({condition}) WITH CHECK ({condition})"
        )
        permissions = "SELECT" if table == "subscriptions" else "SELECT, INSERT, UPDATE, DELETE"
        op.execute(f"GRANT {permissions} ON {table} TO tato_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"REVOKE ALL ON {table} FROM tato_app")
        op.execute(f"DROP POLICY tenant_access ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
