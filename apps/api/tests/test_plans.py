from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import Subscription
from app.plans import FREE, PRO, require_capacity, require_reports, user_plan


@pytest.mark.parametrize(
    ("name", "status", "expected"),
    [
        ("pro", "active", PRO),
        ("pro", "past_due", FREE),
        ("pro", "canceled", FREE),
        ("free", "active", FREE),
    ],
)
def test_plan_comes_from_subscription(name, status, expected):
    owner = uuid4()
    session = Mock()
    session.exec.return_value.first.return_value = Subscription(
        user_id=owner,
        plan=name,
        status=status,
    )
    assert user_plan(session, owner) == expected
    statement = session.exec.call_args.args[0]
    assert owner in statement.compile().params.values()


def test_no_subscription_means_free():
    session = Mock()
    session.exec.return_value.first.return_value = None
    assert user_plan(session, uuid4()) == FREE


@pytest.mark.parametrize(
    ("feature", "limit"),
    [
        ("agents", 1),
        ("messages_per_month", 200),
        ("import_sources", 1),
    ],
)
def test_free_limits_enforced_at_boundary(feature, limit):
    require_capacity(FREE, feature, limit - 1)
    with pytest.raises(HTTPException) as error:
        require_capacity(FREE, feature, limit)
    assert error.value.status_code == 403


def test_pro_still_has_agent_and_technical_limits():
    require_capacity(PRO, "messages_per_month", 10000)
    require_capacity(PRO, "import_sources", 100)
    with pytest.raises(HTTPException):
        require_capacity(PRO, "agents", 3)
    with pytest.raises(ValueError):
        require_capacity(FREE, "agents", -1)
    require_reports(PRO)
    with pytest.raises(HTTPException):
        require_reports(FREE)
    assert PRO.requests_per_minute == 300
