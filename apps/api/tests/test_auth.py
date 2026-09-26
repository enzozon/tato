from typing import Annotated
from uuid import uuid4

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import Identity, current_identity, service_url


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "synthetic-public-key")
    app = FastAPI()

    @app.get("/private")
    def private(identity: Annotated[Identity, Depends(current_identity)]):
        return {"id": str(identity.id)}

    with TestClient(app) as client:
        yield client


def mock_provider(monkeypatch, status, body):
    original = httpx.Client

    def handle(request):
        assert request.url == "https://synthetic.supabase.co/auth/v1/user"
        assert request.headers["authorization"] == "Bearer synthetic-session"
        assert request.headers["apikey"] == "synthetic-public-key"
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        "app.auth.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )


def test_only_provider_identity_is_trusted(auth_client, monkeypatch):
    owner = uuid4()
    mock_provider(monkeypatch, 200, {"id": str(owner), "user_metadata": {"plan": "pro"}})
    response = auth_client.get(
        "/private?user_id=attacker", headers={"Authorization": "Bearer synthetic-session"}
    )
    assert response.json() == {"id": str(owner)}


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {}, 401),
        (403, {}, 401),
        (429, {}, 503),
        (500, {}, 503),
        (200, {"id": "bad"}, 503),
        (200, {"id": str(uuid4()), "is_anonymous": True}, 401),
    ],
)
def test_provider_errors_fail_closed(auth_client, monkeypatch, status, body, expected):
    mock_provider(monkeypatch, status, body)
    response = auth_client.get("/private", headers={"Authorization": "Bearer synthetic-session"})
    assert response.status_code == expected
    assert "synthetic-session" not in response.text


def test_missing_or_oversized_bearer_is_rejected(auth_client):
    assert auth_client.get("/private").status_code == 401
    assert auth_client.get("/private", headers={"Authorization": "Basic abc"}).status_code == 401
    assert (
        auth_client.get("/private", headers={"Authorization": "Bearer " + "a" * 8193}).status_code
        == 401
    )


def test_missing_configuration_fails_closed(auth_client, monkeypatch):
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY")
    assert (
        auth_client.get(
            "/private", headers={"Authorization": "Bearer synthetic-session"}
        ).status_code
        == 503
    )


@pytest.mark.parametrize("url", ["", "http://remote.example", "https://user:pass@example.com"])
def test_unsafe_service_url_rejected(monkeypatch, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(Exception) as error:
        service_url("SUPABASE_URL")
    assert error.value.status_code == 503
