from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.database import tenant_session
from app.models import Category, Subscription

pytestmark = pytest.mark.integration


def test_isolation_and_context_reset(runtime_engine: Engine, owners: tuple[UUID, UUID]) -> None:
    first, second = owners
    with tenant_session(runtime_engine, first) as session:
        category = Category(user_id=first, name="Mercado")
        session.add(category)
    with tenant_session(runtime_engine, second) as session:
        assert session.get(Category, category.id) is None
        assert list(session.exec(select(Category))) == []
    with pytest.raises(DBAPIError), tenant_session(runtime_engine, second) as session:
        session.add(Category(user_id=first, name="Intruso"))
        session.flush()
    with pytest.raises(DBAPIError), tenant_session(runtime_engine, first) as session:
        session.execute(
            text("UPDATE categories SET user_id = :other WHERE id = :id"),
            {"other": second, "id": category.id},
        )
    with Session(runtime_engine) as session:
        assert list(session.exec(select(Category))) == []
        assert session.execute(text("SELECT current_setting('app.user_id', true)")).scalar() in {
            None,
            "",
        }
    with tenant_session(runtime_engine, first) as session:
        assert session.get(Category, category.id) is not None


def test_runtime_cannot_upgrade_plan(runtime_engine: Engine, owners: tuple[UUID, UUID]) -> None:
    with pytest.raises(DBAPIError), tenant_session(runtime_engine, owners[0]) as session:
        session.add(Subscription(user_id=owners[0], plan="pro"))
        session.flush()


def test_runtime_refuses_admin_credentials(admin_engine: Engine, owners: tuple[UUID, UUID]) -> None:
    with pytest.raises(PermissionError), tenant_session(admin_engine, owners[0]):
        pass
