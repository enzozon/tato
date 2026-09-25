import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.engine import make_url
from sqlmodel import Session

from app.database import app_engine
from app.models import User


@pytest.fixture(scope="session")
def admin_engine() -> Iterator[Engine]:
    url = os.environ["TEST_DATABASE_ADMIN_URL"]
    if make_url(url).database != "tato_test":
        pytest.fail("Integração exige banco descartável chamado tato_test.")
    engine = app_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def runtime_engine() -> Iterator[Engine]:
    url = os.environ["TEST_DATABASE_URL"]
    if make_url(url).database != "tato_test":
        pytest.fail("Integração exige banco descartável chamado tato_test.")
    engine = app_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def owners(admin_engine: Engine) -> Iterator[tuple[UUID, UUID]]:
    first, second = uuid4(), uuid4()
    with Session(admin_engine) as session, session.begin():
        session.add_all([User(id=first), User(id=second)])
    yield first, second
    with admin_engine.begin() as connection:
        connection.execute(delete(User).where(User.id.in_([first, second])))
