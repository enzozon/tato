from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import usage
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.chat_history import month_window
from app.llm import LLMUnavailable
from app.main import app


def test_usage_requires_identity_and_sanitizes_failures(monkeypatch):
    with TestClient(app) as client:
        assert client.get("/me/usage").status_code == 401
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    now = datetime(2026, 10, 7, tzinfo=UTC)
    result = usage.Usage(
        plan="free",
        period_start=now,
        period_end=now,
        messages=usage.Capacity.measured(201, 200),
        import_sources=usage.Capacity.measured(1, 1),
        agents=usage.Capacity.measured(1, 1),
    )
    try:
        monkeypatch.setattr(usage, "consumption", lambda engine, identity, moment: result)
        with TestClient(app) as client:
            response = client.get("/me/usage")
            assert response.headers["Cache-Control"] == "no-store"
            assert response.json()["messages"] == {"used": 201, "limit": 200, "remaining": 0}

            def unavailable(*args):
                raise LLMUnavailable("private")

            monkeypatch.setattr(usage, "consumption", unavailable)
            response = client.get("/me/usage")
            assert response.status_code == 409 and "private" not in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("year,month,end_year,end_month", [(2026, 12, 2027, 1), (2028, 2, 2028, 3)])
def test_quota_window_uses_utc_month(year, month, end_year, end_month):
    start, end = month_window(datetime(year, month, 15, tzinfo=timezone(timedelta(hours=-3))))
    assert start == datetime(year, month, 1, tzinfo=UTC)
    assert end == datetime(end_year, end_month, 1, tzinfo=UTC)
    assert usage.Capacity.measured(7, None).remaining is None
