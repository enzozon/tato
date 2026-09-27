import base64
import json
import shutil
import subprocess

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app import account_service, llm_cache
from app.auth import Identity
from app.models import User

pytestmark = pytest.mark.integration


def redis_cli(command):
    docker = shutil.which("docker") or "C:/Program Files/Docker/Docker/resources/bin/docker.exe"
    result = subprocess.run(
        [docker, "compose", "exec", "-T", "redis", "redis-cli", "--json", *map(str, command)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def test_real_redis_expiry_capacity_and_recoverable_deletion(
    runtime_engine, admin_engine, owners, monkeypatch
):
    owner, other = owners
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(b"x" * 32).decode())
    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"y" * 32).decode())
    monkeypatch.setenv("LLM_CACHE", "redis")
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(llm_cache, "redis_command", redis_cli)
    monkeypatch.setattr(account_service, "delete_identity", lambda _: None)
    key = llm_cache.cache_key(owner)
    try:
        llm_cache.put_cached(owner, "field", "{}")
        assert llm_cache.get_cached(owner, "field") == "{}"
        assert llm_cache.get_cached(other, "field") is None
        assert 0 < redis_cli(["TTL", key]) <= 3600
        fields = [item for i in range(64) for item in (str(i), "synthetic")]
        redis_cli(["HSET", key, *fields])
        llm_cache.put_cached(owner, "new", "{}")
        assert redis_cli(["HLEN", key]) == 1
        original_clear = llm_cache.clear_cache

        def unavailable(_):
            raise HTTPException(503, "Redis indisponível.")

        monkeypatch.setattr(llm_cache, "clear_cache", unavailable)
        with pytest.raises(HTTPException):
            account_service.request_deletion(runtime_engine, owner, lambda: Identity(id=owner))
        with Session(admin_engine) as session:
            assert session.get(User, owner).deletion_requested_at is not None
        assert llm_cache.get_cached(owner, "new") == "{}"
        monkeypatch.setattr(llm_cache, "clear_cache", original_clear)
        account_service.finish_deletion(runtime_engine, owner)
        assert redis_cli(["EXISTS", key]) == 0
        with Session(admin_engine) as session:
            assert session.get(User, owner) is None
    finally:
        redis_cli(["DEL", key])
