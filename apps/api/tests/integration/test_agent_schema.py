from datetime import date

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import tenant_session
from app.models import Account, Agent, Goal, User

pytestmark = pytest.mark.integration


def test_agents_are_isolated_and_link_only_owned_records(admin_engine, runtime_engine, owners):
    accounts, goals = [], []
    for owner in owners:
        with tenant_session(runtime_engine, owner) as session:
            account = Account(
                user_id=owner,
                name_ciphertext=b"synthetic",
                kind="checking",
                opening_date=date(2026, 1, 1),
            )
            goal = Goal(user_id=owner, description_ciphertext=b"synthetic", target_cents=10000)
            session.add(account)
            session.add(goal)
            session.flush()
            accounts.append(account.id)
            goals.append(goal.id)
    for account_id, goal_id in [(accounts[1], goals[0]), (accounts[0], goals[1])]:
        with pytest.raises(IntegrityError), tenant_session(runtime_engine, owners[0]) as session:
            session.add(
                Agent(user_id=owners[0], kind="goal", account_id=account_id, goal_id=goal_id)
            )
    agent = Agent(user_id=owners[0], kind="goal", account_id=accounts[0], goal_id=goals[0])
    with tenant_session(runtime_engine, owners[0]) as session:
        session.add(agent)
        session.flush()
        agent_id = agent.id
    with tenant_session(runtime_engine, owners[1]) as session:
        assert session.exec(select(Agent)).all() == []
    with pytest.raises(IntegrityError), admin_engine.begin() as connection:
        connection.execute(
            insert(Agent).values(
                **Agent(
                    user_id=owners[0],
                    kind="runway",
                    account_id=accounts[0],
                    goal_id=goals[0],
                ).model_dump()
            )
        )
    with admin_engine.begin() as connection:
        connection.execute(delete(User).where(User.id == owners[0]))
    with Session(admin_engine) as session:
        assert session.get(Agent, agent_id) is None
