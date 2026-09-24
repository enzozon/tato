import hashlib
import hmac
import os
from threading import Lock
from time import monotonic
from uuid import UUID

import httpx
from fastapi import HTTPException

from app.auth import service_key, service_url
from app.crypto import load_key

RATE_SCRIPT = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
if count >= tonumber(ARGV[1]) then
    return {0, math.max(1, redis.call('TTL', KEYS[1]))}
end
local updated = redis.call('INCR', KEYS[1])
if updated == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return {1, redis.call('TTL', KEYS[1])}
"""
_windows: dict[str, tuple[int, float]] = {}
_lock = Lock()


def rate_key(owner: UUID) -> str:
    digest = hmac.new(load_key("DEDUP_HMAC_KEY"), str(owner).encode(), hashlib.sha256).hexdigest()
    return f"tato:rate:{digest}"


def redis_command(command: list[str | int]) -> object:
    url = service_url("UPSTASH_REDIS_REST_URL")
    token = service_key("UPSTASH_REDIS_REST_TOKEN")
    try:
        with httpx.Client(timeout=3, follow_redirects=False) as client:
            response = client.post(url, headers={"Authorization": f"Bearer {token}"}, json=command)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "error" in payload or "result" not in payload:
            raise ValueError("Resposta inválida.")
        return payload["result"]
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Controle de acesso temporariamente indisponível.") from None


def local_limit(key: str, limit: int) -> tuple[int, int]:
    # ponytail: um processo e até 10 mil identidades; produção exige Redis compartilhado.
    with _lock:
        now = monotonic()
        expired = [entry for entry, (_, end) in _windows.items() if end <= now]
        for entry in expired:
            del _windows[entry]
        if key not in _windows and len(_windows) >= 10000:
            raise HTTPException(503, "Limite de desenvolvimento atingido.")
        count, end = _windows.get(key, (0, now + 60))
        allowed = int(count < limit)
        _windows[key] = (count + allowed, end)
        return allowed, max(1, int(end - now + 0.999))


def memory_mode() -> bool:
    mode = os.environ.get("RATE_LIMIT_BACKEND", "upstash")
    if mode == "memory" and os.environ.get("TATO_ENV") == "development":
        return True
    if mode != "upstash":
        raise HTTPException(503, "Backend de limite não permitido.")
    return False


def check_rate(owner: UUID, limit: int) -> None:
    key = rate_key(owner)
    result = (
        local_limit(key, limit)
        if memory_mode()
        else redis_command(["EVAL", RATE_SCRIPT, 1, key, limit])
    )
    if (
        not isinstance(result, (list, tuple))
        or len(result) != 2
        or any(type(value) is not int for value in result)
        or result[0] not in {0, 1}
        or not 1 <= result[1] <= 60
    ):
        raise HTTPException(503, "Resposta inválida do controle de acesso.")
    if not result[0]:
        raise HTTPException(429, "Muitas requisições.", headers={"Retry-After": str(result[1])})


def clear_rate(owner: UUID) -> None:
    key = rate_key(owner)
    if memory_mode():
        with _lock:
            _windows.pop(key, None)
    else:
        redis_command(["DEL", key])
