import base64
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import account_export as export
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.main import app
from app.models import User
from app.plans import FREE
from tests.test_account_export_record import KEY, personal_records


@pytest.fixture
def ready(monkeypatch):
    owner = uuid4()
    session = Mock()
    session.get.return_value = User(id=owner)
    session.get.return_value.onboarding_completed_at = datetime(2026, 10, 16, tzinfo=UTC)
    rows = personal_records(owner)
    session.exec.side_effect = [[row] for row in rows[:7]] + [
        [rows[10]],
        [rows[9]],
        [rows[7]],
        [rows[8]],
        [rows[11]],
        [rows[12]],
    ]
    active = [False]

    @contextmanager
    def locked(*args):
        active[0] = True
        try:
            yield session
        finally:
            active[0] = False

    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(KEY).decode())
    monkeypatch.setattr(export, "account_session", locked)
    monkeypatch.setattr(export, "user_plan", lambda *args: FREE)
    rate = Mock()
    monkeypatch.setattr(export, "check_rate", rate)
    return owner, session, active, rate


def test_complete_json_materialized_before_unlock(ready):
    owner, session, active, rate = ready
    payload = json.loads(export.export_account(None, owner))
    assert not active[0]
    assert payload["version"] == 1 and payload["user"]["id"] == str(owner)
    assert payload["user"]["onboarding_completed_at"] == "2026-10-16T00:00:00+00:00"
    assert payload["accounts"][0]["name"] == "Carteira demonstrativa"
    assert payload["transactions"][0]["amount_cents"] == "-4200"
    assert len(payload) == 16
    assert session.exec.call_count == 13
    rate.assert_called_once_with(owner, FREE.requests_per_minute)


@pytest.mark.parametrize("limit", ["bytes", "rows"])
def test_limit_never_returns_partial_export(ready, monkeypatch, limit):
    owner, _, active, _ = ready
    monkeypatch.setattr(export, "MAX_EXPORT_BYTES" if limit == "bytes" else "MAX_EXPORT_ROWS", 1)
    with pytest.raises(HTTPException) as error:
        export.export_account(None, owner)
    assert error.value.status_code == 409 and not active[0]


@pytest.mark.parametrize("state", ["missing", "deleting", "rate"])
def test_export_rejects_inactive_or_limited_account(ready, state):
    owner, session, _, rate = ready
    if state == "missing":
        session.get.return_value = None
    elif state == "deleting":
        session.get.return_value.deletion_requested_at = datetime.now(UTC)
    else:
        rate.side_effect = HTTPException(429, "Limite", headers={"Retry-After": "60"})
    with pytest.raises(HTTPException) as error:
        export.export_account(None, owner)
    assert error.value.status_code == (429 if state == "rate" else 409)
    session.exec.assert_not_called()


def test_export_requires_authentication():
    with TestClient(app) as client:
        assert client.get("/me/export").status_code == 401
    assert app.openapi()["paths"]["/me/export"]["get"]["security"] == [{"HTTPBearer": []}]


@pytest.mark.parametrize(
    "failure",
    [
        None,
        InvalidTag("private"),
        ValueError("secret"),
        KeyError("private"),
        HTTPException(409, "Conta indisponível"),
        HTTPException(429, "Aguarde", headers={"Retry-After": "60"}),
    ],
)
def test_download_and_sanitized_failures(monkeypatch, failure):
    owner = uuid4()
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    service = Mock(return_value=b'{"version":1}', side_effect=failure)
    monkeypatch.setattr(export, "export_account", service)
    try:
        with TestClient(app) as client:
            response = client.get("/me/export")
        assert response.headers["cache-control"] == "no-store"
        assert "private" not in response.text and "secret" not in response.text
        if failure is None:
            assert response.status_code == 200
            assert (
                response.headers["content-disposition"] == 'attachment; filename="tato-dados.json"'
            )
            assert response.headers["content-type"] == "application/json"
        else:
            assert response.status_code == (
                failure.status_code if isinstance(failure, HTTPException) else 503
            )
        service.assert_called_once_with(None, owner)
    finally:
        app.dependency_overrides.clear()
