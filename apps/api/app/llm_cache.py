import base64
import hashlib
import hmac
import json
import os
from time import time
from uuid import UUID

from cryptography.exceptions import InvalidTag
from pydantic import BaseModel, ValidationError

from app.crypto import decrypt_text, encrypt_text, load_key
from app.llm import Generation, LLMProvider
from app.rate_limit import rate_key, redis_command

WRITE_CACHE = """
if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 0 and redis.call('HLEN', KEYS[1]) >= 64 then
    redis.call('DEL', KEYS[1])
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], 3600)
return 1
"""


def cache_key(owner: UUID) -> str:
    return rate_key(owner).replace(":rate:", ":llm:")


def fingerprint(request: Generation, output: type[BaseModel], providers: list[LLMProvider]) -> str:
    content = json.dumps(
        [
            "v1",
            request.model_dump(),
            output.model_json_schema(),
            [(p.name, p.model) for p in providers],
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hmac.new(load_key("DEDUP_HMAC_KEY"), content.encode(), hashlib.sha256).hexdigest()


def get_cached(owner: UUID, field: str) -> str | None:
    raw = redis_command(["HGET", cache_key(owner), field])
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(
            decrypt_text(
                base64.b64decode(raw, validate=True),
                load_key("DATA_ENCRYPTION_KEY"),
                owner,
                f"llm-cache:{field}",
            )
        )
        if type(payload["expires"]) not in {int, float} or payload["expires"] <= time():
            return None
        return payload["content"] if isinstance(payload["content"], str) else None
    except (ValueError, KeyError, TypeError, InvalidTag, ValidationError):
        return None


def put_cached(owner: UUID, field: str, content: str) -> None:
    payload = json.dumps({"expires": time() + 3600, "content": content})
    encrypted = encrypt_text(payload, load_key("DATA_ENCRYPTION_KEY"), owner, f"llm-cache:{field}")
    result = redis_command(
        ["EVAL", WRITE_CACHE, 1, cache_key(owner), field, base64.b64encode(encrypted).decode()]
    )
    if result != 1:
        raise ValueError("Resposta inválida do cache.")


def clear_cache(owner: UUID) -> None:
    redis_command(["DEL", cache_key(owner)])


def clear_configured_cache(owner: UUID) -> None:
    if os.environ.get("LLM_CACHE") == "redis" or os.environ.get("UPSTASH_REDIS_REST_URL"):
        clear_cache(owner)
