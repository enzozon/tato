import base64
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app import rate_limit as rate


@pytest.fixture(autouse=True)
def local_environment(monkeypatch):
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"s" * 32).decode())
    rate._windows.clear()


def test_window_is_per_owner_and_expires(monkeypatch):
    first, second = uuid4(), uuid4()
    monkeypatch.setattr(rate, "monotonic", lambda: 100)
    rate.check_rate(first, 1)
    rate.check_rate(second, 1)
    with pytest.raises(HTTPException) as error:
        rate.check_rate(first, 1)
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "60"}
    monkeypatch.setattr(rate, "monotonic", lambda: 161)
    rate.check_rate(first, 1)
    rate.clear_rate(first)
    assert rate.rate_key(first) not in rate._windows
    assert str(first) not in rate.rate_key(first)


def test_memory_is_forbidden_outside_development(monkeypatch):
    monkeypatch.setenv("TATO_ENV", "production")
    with pytest.raises(HTTPException) as error:
        rate.check_rate(uuid4(), 60)
    assert error.value.status_code == 503


@pytest.mark.parametrize("result", [[0, 12], [True, 60], [1], "bad", [1, -1]])
def test_remote_response_is_checked(monkeypatch, result):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "upstash")
    monkeypatch.setattr(rate, "redis_command", lambda command: result)
    with pytest.raises(HTTPException) as error:
        rate.check_rate(uuid4(), 60)
    assert error.value.status_code == (429 if result == [0, 12] else 503)


@pytest.mark.parametrize(
    ("status", "body"), [(500, {}), (200, {"error": "private"}), (200, {"result": [1, 60]})]
)
def test_rest_transport(monkeypatch, status, body):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "upstash")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://synthetic.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "synthetic-token")
    original = httpx.Client
    monkeypatch.setattr(
        rate.httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda req: httpx.Response(status, json=body)), **kwargs
        ),
    )
    if "result" in body:
        rate.check_rate(uuid4(), 60)
        rate.clear_rate(uuid4())
    else:
        with pytest.raises(HTTPException) as error:
            rate.check_rate(uuid4(), 60)
        assert error.value.status_code == 503
