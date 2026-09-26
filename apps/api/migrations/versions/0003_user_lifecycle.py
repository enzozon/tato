"""Campos opcionais de ciclo de conta aprovados pelo Enzo."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("users", "deletion_requested_at")
    op.drop_column("users", "onboarding_completed_at")
