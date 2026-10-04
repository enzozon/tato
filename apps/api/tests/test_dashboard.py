from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.dashboard import Dashboard
from app.main import app


def test_dashboard_contract_and_cors(monkeypatch):
    result = Dashboard(
        as_of=date(2026, 10, 4),
        month_start=date(2026, 10, 1),
        accounts=[],
        balance_cents=str(2**60),
        expense_cents="0",
        categories=[],
    )
    monkeypatch.setattr("app.dashboard.summary", lambda *args: result)
    app.dependency_overrides[current_identity] = lambda: Identity(id=uuid4())
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/dashboard", headers={"Origin": "http://127.0.0.1:3000"})
            assert response.json()["balance_cents"] == str(2**60)
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
            response = client.options(
                "/dashboard",
                headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "GET"},
            )
            assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
