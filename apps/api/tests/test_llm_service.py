from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import llm_service as service
from app.llm import Generation, LLMUnavailable, MoneyAnswer
from app.llm_router import Routed
from app.models import User


def test_disabled_by_default_and_free_tier_confirmation(monkeypatch):
    service.runtime_router.cache_clear()
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    assert service.runtime_router().providers == []
    service.runtime_router.cache_clear()
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.delenv("LLM_FREE_TIER_CONFIRMED", raising=False)
    with pytest.raises(LLMUnavailable):
        service.runtime_router()
    service.runtime_router.cache_clear()


@pytest.mark.parametrize("cache_state", ["hit", "miss", "failure", "invalid"])
def test_service_revalidates_cache_and_account(monkeypatch, cache_state):
    owner = uuid4()
    value = MoneyAnswer(source_id="total", amount_cents=4200)
    session = Mock()
    session.get.return_value = User(id=owner)
    router = Mock()
    router.generate.return_value = Routed(value, ())

    @contextmanager
    def transaction(*args):
        yield session

    monkeypatch.setattr(service, "account_session", transaction)
    monkeypatch.setattr(service, "runtime_router", lambda: router)
    monkeypatch.setenv("LLM_CACHE", "redis")
    monkeypatch.setattr(service.llm_cache, "fingerprint", lambda *args: "field")
    cache_read = Mock(return_value=value.model_dump_json() if cache_state == "hit" else None)
    if cache_state == "failure":
        cache_read.side_effect = HTTPException(503)
    if cache_state == "invalid":
        cache_read.return_value = value.model_copy(update={"amount_cents": 99}).model_dump_json()
    monkeypatch.setattr(service.llm_cache, "get_cached", cache_read)
    write = Mock()
    monkeypatch.setattr(service.llm_cache, "put_cached", write)
    request = Generation(instruction="total", data="sintetico", classification="synthetic")
    result = service.generate(Mock(), owner, request, MoneyAnswer, lambda x: x.amount_cents == 4200)
    assert result.cached == (cache_state == "hit")
    assert router.generate.call_count == int(cache_state != "hit")
    session.get.side_effect = [User(id=owner), None]
    cache_read.side_effect, cache_read.return_value = None, None
    write.reset_mock()
    with pytest.raises(LLMUnavailable):
        service.generate(Mock(), owner, request, MoneyAnswer, lambda _: True)
    write.assert_not_called()
