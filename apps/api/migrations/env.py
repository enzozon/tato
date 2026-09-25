import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401 — registra metadados para comparação

url = os.environ["DATABASE_MIGRATION_URL"]

if context.is_offline_mode():
    context.configure(url=url, target_metadata=SQLModel.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=SQLModel.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
