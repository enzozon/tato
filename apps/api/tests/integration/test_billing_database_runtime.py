import os

import pytest
from sqlalchemy import event, text

from app import billing_database
from app.database import app_engine
from app.models import Subscription

pytestmark = pytest.mark.integration


@pytest.fixture
def billing_runtime():
    engine = app_engine(os.environ["TEST_DATABASE_ADMIN_URL"])

    @event.listens_for(engine, "connect")
    def restrict(connection, record):
        connection.autocommit = True
        connection.execute("SET ROLE tato_billing")
        connection.autocommit = False

    yield engine
    engine.dispose()


def test_factory_checks_effective_postgres_role_without_password_rotation(
    billing_runtime, runtime_engine, owners, monkeypatch
):
    billing_database.billing_engine.cache_clear()
    monkeypatch.setenv(
        "BILLING_DATABASE_URL", "postgresql+psycopg://tato_billing@127.0.0.1/tato_test"
    )
    monkeypatch.setattr(billing_database, "app_engine", lambda _: billing_runtime)
    try:
        assert billing_database.billing_engine() is billing_runtime
        with billing_database.billing_account_session(billing_runtime, owners[0]) as session:
            assert session.scalar(text("SELECT current_user")) == "tato_billing"
            session.add(Subscription(user_id=owners[0], plan="pro"))
        with (
            pytest.raises(PermissionError),
            billing_database.billing_account_session(runtime_engine, owners[0]),
        ):
            pass
        billing_database.billing_engine.cache_clear()
        monkeypatch.setattr(billing_database, "app_engine", lambda _: runtime_engine)
        with pytest.raises(PermissionError):
            billing_database.billing_engine()
    finally:
        billing_database.billing_engine.cache_clear()
