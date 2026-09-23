"""Gera a primeira revision a partir dos modelos; não sobrescreve histórico existente."""

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import SQLModel

import app.models  # noqa: F401 — registra as tabelas

target = Path("apps/api/migrations/versions/0001_schema.py")
tables = SQLModel.metadata.sorted_tables
statements = ["CREATE EXTENSION IF NOT EXISTS vector;"]
for table in tables:
    statements.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() + ";")
    for index in sorted(table.indexes, key=lambda item: item.name or ""):
        statements.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ";")

target.parent.mkdir(parents=True, exist_ok=True)
with target.open("x", encoding="utf-8", newline="\n") as output:
    output.write('"""Schema inicial gerado por SQLAlchemy e revisado antes da execução."""\n\n')
    output.write('from alembic import op\n\nrevision = "0001"\ndown_revision = None\n')
    output.write("branch_labels = None\ndepends_on = None\n\n\n")
    output.write('def upgrade() -> None:\n    op.execute("""\n')
    output.write("\n".join(line.rstrip() for line in "\n\n".join(statements).splitlines()))
    output.write('\n    """)\n\n\ndef downgrade() -> None:\n')
    for table in reversed(tables):
        output.write(f'    op.drop_table("{table.name}")\n')
