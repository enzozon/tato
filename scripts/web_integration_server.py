"""Servidor exclusivo do teste web: localhost, banco tato_test e identidade sintética."""

import base64
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlmodel import Session


def main() -> None:
    for target, source in [
        ("DATABASE_URL", "TEST_DATABASE_URL"),
        ("DATABASE_MIGRATION_URL", "TEST_DATABASE_ADMIN_URL"),
    ]:
        url = make_url(os.environ.get(source) or os.environ[target])
        if url.host not in {"127.0.0.1", "localhost", "postgres"}:
            raise SystemExit("Teste web exige Postgres local.")
        os.environ[target] = url.set(database="tato_test").render_as_string(hide_password=False)
    for name, value in [
        ("LLM_ENABLED", "false"),
        ("LLM_CACHE", "off"),
        ("RATE_LIMIT_BACKEND", "memory"),
        ("TATO_ENV", "development"),
        ("AGENT_EMAIL_ENABLED", "false"),
        ("WEB_ORIGINS", "http://127.0.0.1:3001"),
    ]:
        os.environ[name] = value
    for name in ["DATA_ENCRYPTION_KEY", "DEDUP_HMAC_KEY"]:
        os.environ[name] = base64.b64encode(b"s" * 32).decode()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
    import uvicorn
    from fastapi import HTTPException

    from app import account_routes
    from app.auth import Identity, current_identity
    from app.database import app_engine
    from app.main import app
    from app.models import User

    owner = UUID("00000000-0000-4000-8000-000000000e2e")
    engine = app_engine(os.environ["DATABASE_MIGRATION_URL"])
    with Session(engine) as session, session.begin():
        session.execute(delete(User).where(User.id == owner))
        session.add(User(id=owner))

    def identity(credentials: account_routes.CredentialsDep) -> Identity:
        if credentials is None or credentials.credentials != "synthetic-token":
            raise HTTPException(401, "Identidade sintética obrigatória.")
        return Identity(id=owner)

    app.dependency_overrides[current_identity] = identity
    account_routes.current_identity = identity
    try:
        uvicorn.run(app, host="127.0.0.1", port=8009, access_log=False, log_level="warning")
    finally:
        with engine.begin() as connection:
            connection.execute(delete(User).where(User.id == owner))
        engine.dispose()


if __name__ == "__main__":
    main()
