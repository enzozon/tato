from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import import_setup as setup
from app.account_routes import runtime_engine
from app.auth import Identity, current_identity
from app.crypto import decrypt_text
from app.main import app
from app.models import User


def test_setup_validation_and_encryption(monkeypatch):
    owner = uuid4()
    session = Mock()
    session.get.return_value = User(id=owner)
    session.exec.side_effect = [Mock(all=lambda: []), Mock(first=lambda: None)]

    @contextmanager
    def transaction(*args):
        yield session

    monkeypatch.setattr(setup, "account_session", transaction)
    monkeypatch.setattr(setup, "check_rate", lambda *args: None)
    monkeypatch.setattr(setup, "user_plan", lambda *args: Mock(requests_per_minute=60))
    monkeypatch.setattr(setup, "load_key", lambda *args: b"x" * 32)
    app.dependency_overrides[current_identity] = lambda: Identity(id=owner)
    app.dependency_overrides[runtime_engine] = lambda: None
    try:
        with TestClient(app) as client:
            data = {"name": "Conta teste", "kind": "checking", "opening_date": "2026-01-01"}
            result = client.post("/accounts", json=data)
            assert result.status_code == 201
            assert result.headers["cache-control"] == "no-store"
            account = session.add.call_args.args[0]
            assert (
                decrypt_text(account.name_ciphertext, b"x" * 32, owner, "account") == data["name"]
            )
            for invalid in [True, 1.5, "42", 2**63]:
                assert (
                    client.post(
                        "/accounts", json=data | {"opening_balance_cents": invalid}
                    ).status_code
                    == 422
                )
            assert (
                client.post("/accounts", json=data | {"user_id": str(uuid4())}).status_code == 422
            )
            result = client.post("/rules", json={"category": "Compras", "pattern": "mercado"})
            assert result.status_code == 201
            rule = session.add.call_args.args[0]
            assert decrypt_text(rule.pattern_ciphertext, b"x" * 32, owner, "rule") == "mercado"
            session.get.return_value = None
            assert client.post("/accounts", json=data).status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["/accounts", "/rules"])
def test_setup_requires_auth(path):
    with TestClient(app) as client:
        assert client.post(path, json={}).status_code == 401
