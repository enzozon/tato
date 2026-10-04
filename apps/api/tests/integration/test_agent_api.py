import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.account_routes import runtime_engine as engine_dependency
from app.account_service import account_session
from app.auth import Identity, current_identity
from app.main import app
from app.models import Account
from tests.integration.test_agent_config import agent_accounts as agent_accounts

pytestmark = pytest.mark.integration


def test_configuration_cron_inbox_and_read_are_isolated(
    runtime_engine, owners, agent_accounts, monkeypatch
):
    owner = owners[0]
    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"y" * 32).decode())
    monkeypatch.setenv("AGENTS_RUN_TOKEN", "z" * 32)
    with account_session(runtime_engine, owner) as session:
        session.execute(
            update(Account)
            .where(Account.id == agent_accounts[0])
            .values(opening_balance_cents=10000)
        )
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[engine_dependency] = lambda: runtime_engine
    try:
        with TestClient(app) as client:
            goal = client.post(
                "/goals", json={"description": "Reserva sintética", "target_cents": 10000}
            )
            assert goal.status_code == 201
            assert client.get("/goals").json()[0]["description"] == "Reserva sintética"
            configured = client.put(
                "/agents/goal",
                json={"account_id": str(agent_accounts[0]), "goal_id": goal.json()["id"]},
            )
            assert configured.status_code == 200
            headers = {"Authorization": "Bearer " + "z" * 32}
            for count in [1, 0]:
                result = client.post(
                    "/internal/agents/run", headers=headers, json={"user_ids": [str(owner)]}
                )
                assert result.status_code == 200 and result.json()["inserted"] == count
            items = client.get("/insights").json()
            assert items[0]["signal"]["facts"]["balance_cents"] == 10000
            insight_id = items[0]["id"]
            assert client.post(f"/insights/{insight_id}/read").status_code == 204
            assert client.get("/insights").json()[0]["read_at"] is not None
            app.dependency_overrides[current_identity] = lambda: Identity(id=owners[1])
            assert client.get("/insights").json() == []
            assert client.post(f"/insights/{insight_id}/read").status_code == 404
    finally:
        app.dependency_overrides.clear()
