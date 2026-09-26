from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlmodel import Session

from app.auth import Identity, delete_identity
from app.database import tenant_session
from app.models import User
from app.plans import Plan, user_plan
from app.rate_limit import check_rate, clear_rate


class Profile(BaseModel):
    id: UUID
    onboarding_completed: bool
    plan: Plan


@contextmanager
def account_session(engine: Engine, owner: UUID) -> Iterator[Session]:
    with tenant_session(engine, owner) as session:
        session.execute(text("SET LOCAL lock_timeout = '5s'"))
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": owner.int % (2**63)})
        yield session


def ensure_user(session: Session, owner: UUID, verify: Callable[[], Identity]) -> User:
    user = session.get(User, owner)
    if user is None:
        # Revalidar sob lock impede recriar uma conta removida após autenticação inicial.
        if verify().id != owner:
            raise HTTPException(401, "Identidade alterada.")
        user = User(id=owner)
        session.add(user)
        session.flush()
    return user


def profile(
    engine: Engine, owner: UUID, verify: Callable[[], Identity], *, complete: bool = False
) -> Profile:
    with account_session(engine, owner) as session:
        user = ensure_user(session, owner, verify)
        if user.deletion_requested_at is not None:
            raise HTTPException(409, "Exclusão de conta pendente.")
        plan = user_plan(session, owner)
        check_rate(owner, plan.requests_per_minute)
        if complete and user.onboarding_completed_at is None:
            user.onboarding_completed_at = datetime.now(UTC)
            session.add(user)
        result = Profile(
            id=owner, onboarding_completed=user.onboarding_completed_at is not None, plan=plan
        )
    return result


def request_deletion(engine: Engine, owner: UUID, verify: Callable[[], Identity]) -> None:
    with account_session(engine, owner) as session:
        user = ensure_user(session, owner, verify)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        if user.deletion_requested_at is None:
            user.deletion_requested_at = datetime.now(UTC)
            session.add(user)
    # O marcador precisa estar confirmado antes de efeitos em serviços externos.
    finish_deletion(engine, owner)


def finish_deletion(engine: Engine, owner: UUID) -> None:
    """Também usado na retomada operacional, quando o login já foi removido."""
    with account_session(engine, owner) as session:
        user = session.get(User, owner)
        if user is None:
            return
        if user.deletion_requested_at is None:
            raise ValueError("Conta não solicitou exclusão.")
        delete_identity(owner)
        clear_rate(owner)
        session.delete(user)
