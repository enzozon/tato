from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session


def app_engine(url: str) -> Engine:
    if make_url(url).drivername != "postgresql+psycopg":
        raise ValueError("Use PostgreSQL com psycopg; SQLite não valida RLS nem vetores.")
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


@contextmanager
def tenant_session(engine: Engine, user_id: UUID) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session, session.begin():
        privileged = session.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()
        if privileged:
            raise PermissionError("A API não pode usar superuser nem BYPASSRLS.")
        session.execute(
            text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(user_id)}
        )
        yield session
