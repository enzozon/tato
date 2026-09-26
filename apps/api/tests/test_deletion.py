from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app import account_service as service
from app.auth import delete_identity
from app.models import User
from app.plans import FREE


@pytest.mark.parametrize(
    ("status", "body", "ok"),
    [
        (200, {}, True),
        (404, {"code": "user_not_found"}, True),
        (404, {}, False),
        (500, {"secret": "never expose"}, False),
        (302, {}, False),
    ],
)
def test_delete_provider_requires_confirmed_removal(monkeypatch, status, body, ok):
    owner = uuid4()
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "synthetic-secret")
    original = httpx.Client

    def handle(request):
        assert request.method == "DELETE"
        assert request.url.path.endswith(str(owner))
        assert request.headers["apikey"] == "synthetic-secret"
        assert request.content == b'{"should_soft_delete":false}'
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        "app.auth.httpx.Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(handle),
            **kwargs,
        ),
    )
    if ok:
        delete_identity(owner)
    else:
        with pytest.raises(HTTPException) as error:
            delete_identity(owner)
        assert error.value.status_code == 503
        assert "never expose" not in error.value.detail


def test_marker_commits_before_external_call_and_retry(monkeypatch):
    owner = uuid4()
    user = User(id=owner)
    session = Mock()
    session.get.return_value = user
    events = []

    @contextmanager
    def transaction(engine, identity):
        assert identity == owner
        yield session
        events.append("commit")

    def failed_delete(identity):
        assert user.deletion_requested_at is not None
        assert events == ["commit"]
        raise HTTPException(503)

    monkeypatch.setattr(service, "account_session", transaction)
    monkeypatch.setattr(service, "check_rate", lambda *args: None)
    monkeypatch.setattr(service, "user_plan", lambda *args: FREE)
    monkeypatch.setattr(service, "delete_identity", failed_delete)
    with pytest.raises(HTTPException):
        service.request_deletion(Mock(), owner, Mock())
    session.delete.assert_not_called()
    monkeypatch.setattr(service, "delete_identity", lambda identity: events.append("auth"))
    monkeypatch.setattr(service, "clear_rate", lambda identity: events.append("rate"))
    service.finish_deletion(Mock(), owner)
    assert events == ["commit", "auth", "rate", "commit"]
    session.delete.assert_called_once_with(user)
    session.get.return_value = None
    service.finish_deletion(Mock(), owner)
    session.get.return_value = User(id=owner)
    with pytest.raises(ValueError):
        service.finish_deletion(Mock(), owner)
