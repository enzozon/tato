import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from app.account_service import account_session
from app.database import app_engine


def require_billing_role(session: Session) -> None:
    role, privileged = session.execute(
        text(
            "SELECT current_user, rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole "
            "OR rolreplication OR rolinherit FROM pg_roles WHERE rolname = current_user"
        )
    ).one()
    if role != "tato_billing" or privileged:
        raise PermissionError("Cobrança exige papel efetivo tato_billing restrito.")


@lru_cache(maxsize=1)
def billing_engine() -> Engine:
    url = os.environ.get("BILLING_DATABASE_URL", "")
    if not url or make_url(url).username != "tato_billing":
        raise PermissionError("Conexão de cobrança não configurada.")
    engine = app_engine(url)
    try:
        with Session(engine) as session:
            require_billing_role(session)
    except Exception:
        engine.dispose()
        raise
    return engine


@contextmanager
def billing_account_session(engine: Engine, owner: UUID) -> Iterator[Session]:
    with account_session(engine, owner) as session:
        require_billing_role(session)
        yield session
