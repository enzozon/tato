from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import account_service as service
from app.auth import Identity
from app.models import User
from app.plans import FREE


@pytest.fixture
def session(monkeypatch):
    session = Mock()

    @contextmanager
    def transaction(engine, owner):
        yield session

    monkeypatch.setattr(service, "account_session", transaction)
    monkeypatch.setattr(service, "user_plan", lambda session, owner: FREE)
    monkeypatch.setattr(service, "check_rate", lambda owner, limit: None)
    return session


def test_first_profile_revalidates_and_onboarding_is_idempotent(session):
    owner = uuid4()
    session.get.return_value = None
    verify = Mock(return_value=Identity(id=owner))
    output = service.profile(Mock(), owner, verify, complete=True)
    assert output.onboarding_completed and output.plan == FREE
    verify.assert_called_once()
    user = session.add.call_args.args[0]
    completed = user.onboarding_completed_at
    session.get.return_value = user
    service.profile(Mock(), owner, verify, complete=True)
    assert user.onboarding_completed_at == completed
    verify.assert_called_once()


def test_pending_deletion_blocks_profile(session):
    owner = uuid4()
    session.get.return_value = User(id=owner, deletion_requested_at=datetime.now(UTC))
    with pytest.raises(HTTPException) as error:
        service.profile(Mock(), owner, Mock())
    assert error.value.status_code == 409


def test_stale_identity_cannot_provision(session):
    session.get.return_value = None
    with pytest.raises(HTTPException):
        service.profile(Mock(), uuid4(), lambda: Identity(id=uuid4()))
    session.add.assert_not_called()
