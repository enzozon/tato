from io import StringIO

import pytest
from alembic import command
from alembic.config import Config


def test_migrations_render_without_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_MIGRATION_URL", "postgresql+psycopg://unused/unused")
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    assert "COMMIT;" in output.getvalue()
    output.seek(0)
    output.truncate()
    command.downgrade(config, "head:base", sql=True)
    assert "DROP TABLE" in output.getvalue()
