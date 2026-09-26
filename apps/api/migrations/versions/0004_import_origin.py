"""Vínculos de origem aprovados antes da importação."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_documents_account_id",
        "documents",
        "accounts",
        ["user_id", "account_id"],
        ["user_id", "id"],
    )
    op.create_index("ix_documents_user_account", "documents", ["user_id", "account_id"])
    op.add_column("transactions", sa.Column("document_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_transactions_document_id",
        "transactions",
        "documents",
        ["user_id", "document_id"],
        ["user_id", "id"],
    )
    op.create_index("ix_transactions_user_document", "transactions", ["user_id", "document_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_user_document", table_name="transactions")
    op.drop_constraint("fk_transactions_document_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "document_id")
    op.drop_index("ix_documents_user_account", table_name="documents")
    op.drop_constraint("fk_documents_account_id", "documents", type_="foreignkey")
    op.drop_column("documents", "account_id")
