from contextlib import contextmanager

import pytest

from app import billing_database


def test_billing_factory_refuses_missing_or_administrative_url(monkeypatch):
    billing_database.billing_engine.cache_clear()
    for value in [
        "",
        "postgresql+psycopg://postgres@127.0.0.1/tato_test",
        "postgresql+psycopg://tato_app@127.0.0.1/tato_test",
    ]:
        monkeypatch.setenv("BILLING_DATABASE_URL", value)
        with pytest.raises(PermissionError):
            billing_database.billing_engine()


@pytest.mark.parametrize(
    "role,privileged",
    [("postgres", False), ("tato_app", False), ("tato_billing", True), ("tato_billing", False)],
)
def test_factory_checks_effective_role_and_disposes_failed_engine(monkeypatch, role, privileged):
    class Result:
        def one(self):
            return role, privileged

    class Session:
        def execute(self, statement):
            return Result()

    class Engine:
        disposed = False

        def dispose(self):
            self.disposed = True

    @contextmanager
    def session(engine):
        yield Session()

    engine = Engine()
    billing_database.billing_engine.cache_clear()
    monkeypatch.setenv(
        "BILLING_DATABASE_URL", "postgresql+psycopg://tato_billing@127.0.0.1/tato_test"
    )
    monkeypatch.setattr(billing_database, "app_engine", lambda _: engine)
    monkeypatch.setattr(billing_database, "Session", session)
    try:
        if role == "tato_billing" and not privileged:
            assert billing_database.billing_engine() is engine
            assert not engine.disposed
        else:
            with pytest.raises(PermissionError):
                billing_database.billing_engine()
            assert engine.disposed
    finally:
        billing_database.billing_engine.cache_clear()
