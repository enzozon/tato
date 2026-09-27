import base64
from uuid import uuid4

import pytest

from app import llm_cache as cache
from app.llm import Generation, MoneyAnswer


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", base64.b64encode(b"x" * 32).decode())
    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"y" * 32).decode())
    data = {}

    def command(args):
        if args[0] == "EVAL":
            data[(args[3], args[4])] = args[5]
            return 1
        if args[0] == "DEL":
            for key in list(data):
                if key[0] == args[1]:
                    del data[key]
            return 1
        return data.get((args[1], args[2]))

    monkeypatch.setattr(cache, "redis_command", command)
    return data


def test_cache_is_encrypted_bound_to_owner_and_request(storage):
    owner, other = uuid4(), uuid4()
    cache.put_cached(owner, "field", '"private text"')
    assert cache.get_cached(owner, "field") == '"private text"'
    assert cache.get_cached(other, "field") is None
    raw = storage[(cache.cache_key(owner), "field")]
    assert "private text" not in raw
    storage[(cache.cache_key(other), "field")] = raw
    storage[(cache.cache_key(owner), "different")] = raw
    assert cache.get_cached(other, "field") is None
    assert cache.get_cached(owner, "different") is None
    cache.clear_cache(owner)
    assert cache.get_cached(owner, "field") is None


def test_expiry_and_changed_request_invalidate_cache(storage, monkeypatch):
    monkeypatch.setattr(cache, "time", lambda: 100)
    owner = uuid4()
    cache.put_cached(owner, "field", "{}")
    monkeypatch.setattr(cache, "time", lambda: 3701)
    assert cache.get_cached(owner, "field") is None
    first = Generation(instruction="x", data="a", classification="synthetic")
    second = first.model_copy(update={"data": "b"})
    assert cache.fingerprint(first, MoneyAnswer, []) != cache.fingerprint(second, MoneyAnswer, [])
