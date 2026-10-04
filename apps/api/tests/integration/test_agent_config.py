import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.account_service import account_session
from app.agent_config import AgentInput, GoalInput, configure, create_goal, list_agents
from app.models import Account, Subscription

pytestmark = pytest.mark.integration


@pytest.fixture
def agent_accounts(runtime_engine, owners, monkeypatch):
    monkeypatch.setattr("app.agent_config.check_rate", lambda *args: None)
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(b"x" * 32).decode())
    result = []
    for owner in owners:
        with account_session(runtime_engine, owner) as session:
            account = Account(
                user_id=owner,
                kind="checking",
                name_ciphertext=b"test",
                opening_date=date(2026, 1, 1),
            )
            session.add(account)
            session.flush()
            result.append(account.id)
    return result


def test_configuration_quota_is_atomic(runtime_engine, admin_engine, owners, agent_accounts):
    owner, account = owners[0], agent_accounts[0]

    def activate(kind):
        try:
            configure(runtime_engine, owner, kind, AgentInput(account_id=account))
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(activate, ["runway", "anomaly"])) == [200, 403]
    assert len(list_agents(runtime_engine, owner)) == 1
    with Session(admin_engine) as session, session.begin():
        session.add(Subscription(user_id=owner, plan="pro", status="active"))
    for kind in ["runway", "anomaly", "subscription_watch"]:
        assert activate(kind) == 200
    goal = create_goal(
        runtime_engine, owner, GoalInput(description="Meta sintética", target_cents=100)
    )
    with pytest.raises(HTTPException) as error:
        configure(runtime_engine, owner, "goal", AgentInput(account_id=account, goal_id=goal))
    assert error.value.status_code == 403
    configure(runtime_engine, owner, "runway", AgentInput(account_id=account, enabled=False))
    configure(runtime_engine, owner, "goal", AgentInput(account_id=account, goal_id=goal))
    assert not list_agents(runtime_engine, owners[1])


def test_configuration_rejects_cross_owner_and_wrong_goal(runtime_engine, owners, agent_accounts):
    with pytest.raises(HTTPException) as error:
        configure(runtime_engine, owners[0], "runway", AgentInput(account_id=agent_accounts[1]))
    assert error.value.status_code == 404
    goal = create_goal(
        runtime_engine, owners[1], GoalInput(description="Outra meta", target_cents=100)
    )
    with pytest.raises(HTTPException) as error:
        configure(
            runtime_engine,
            owners[0],
            "goal",
            AgentInput(account_id=agent_accounts[0], goal_id=goal),
        )
    assert error.value.status_code == 404
