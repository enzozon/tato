import pytest

from app.database import app_engine


def test_runtime_rejects_non_postgres_and_hides_parameters() -> None:
    with pytest.raises(ValueError):
        app_engine("sqlite://")
    engine = app_engine("postgresql+psycopg://unused/unused")
    assert engine.hide_parameters
    engine.dispose()
