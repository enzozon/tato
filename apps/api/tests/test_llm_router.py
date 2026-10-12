import json
import logging
from unittest.mock import Mock

import pytest

from app.llm import Completion, Generation, LLMUnavailable, MoneyAnswer, ProviderError, verify_money
from app.llm_router import Router

REQUEST = Generation(instruction="total", data="sintetico", classification="synthetic")


def provider(name, response):
    result = Mock()
    result.name, result.model = name, "synthetic-model"
    result.generate.side_effect = response if isinstance(response, list) else [response]
    return result


def completion(amount=4200):
    return Completion(
        content=MoneyAnswer(source_id="total", amount_cents=amount).model_dump_json(),
        input_tokens=10,
        output_tokens=5,
    )


def test_429_fallback_circuit_and_exact_financial_guard():
    groq = provider("groq", ProviderError("http_429", cooldown=120))
    gemini = provider("gemini", [completion(9999), completion()])
    last = provider("openrouter", [completion(), completion()])
    router = Router([last, gemini, groq])

    def guard(answer):
        return verify_money(answer, {"total": 4200})

    result = router.generate(REQUEST, MoneyAnswer, guard)
    assert result.value.amount_cents == 4200
    assert [a.outcome for a in result.attempts] == ["error", "invalid", "ok"]
    second = router.generate(REQUEST, MoneyAnswer, guard)
    assert [a.outcome for a in second.attempts] == ["circuit_open", "circuit_open", "ok"]
    assert groq.generate.call_count == gemini.generate.call_count == 1


def test_transient_retry_is_bounded(monkeypatch):
    waits = []
    monkeypatch.setattr("app.llm_router.sleep", waits.append)
    groq = provider("groq", [ProviderError("timeout", retryable=True), completion()])
    result = Router([groq]).generate(REQUEST, MoneyAnswer, lambda _: True)
    assert len(result.attempts) == 2 and waits == [0.25]
    assert result.attempts[0].input_tokens is None


def test_invalid_json_and_private_data_fail_closed():
    groq = provider("groq", Completion(content="not-json", input_tokens=1, output_tokens=1))
    router = Router([groq])
    with pytest.raises(LLMUnavailable) as error:
        router.generate(REQUEST, MoneyAnswer, lambda _: True)
    assert error.value.attempts[0].outcome == "invalid"
    with pytest.raises(LLMUnavailable):
        router.generate(Generation(instruction="x", data="secret"), MoneyAnswer, lambda _: True)
    assert groq.generate.call_count == 1


def test_expired_circuit_can_probe_again():
    groq = provider("groq", [ProviderError("http_401"), completion()])
    router = Router([groq])
    with pytest.raises(LLMUnavailable):
        router.generate(REQUEST, MoneyAnswer, lambda _: True)
    router.blocked_until["groq"] = 0
    assert router.generate(REQUEST, MoneyAnswer, lambda _: True).value.amount_cents == 4200


def test_opt_in_usage_logs_only_technical_fields(monkeypatch, caplog):
    monkeypatch.setenv("LLM_LOG_USAGE", "true")
    caplog.set_level(logging.INFO, logger="tato.llm_usage")
    request = Generation(
        instruction="private-instruction", data="private-data", classification="synthetic"
    )
    router = Router(
        [provider("groq", ProviderError("private-token")), provider("gemini", completion())]
    )
    router.generate(request, MoneyAnswer, lambda _: True)
    events = [json.loads(record.message) for record in caplog.records]
    assert [event["outcome"] for event in events] == ["error", "ok"]
    assert events[0]["input_tokens"] is None and events[1]["input_tokens"] == 10
    assert all(
        set(event)
        == {"event", "provider", "outcome", "input_tokens", "output_tokens", "elapsed_ms"}
        for event in events
    )
    assert "private" not in caplog.text and "synthetic-model" not in caplog.text


def test_usage_logging_defaults_off_and_failure_does_not_block(monkeypatch, caplog):
    monkeypatch.delenv("LLM_LOG_USAGE", raising=False)
    caplog.set_level(logging.INFO, logger="tato.llm_usage")
    Router([provider("groq", completion())]).generate(REQUEST, MoneyAnswer, lambda _: True)
    assert not caplog.records
    monkeypatch.setenv("LLM_LOG_USAGE", "true")
    monkeypatch.setattr(
        "app.llm_router.usage_logger.info", Mock(side_effect=RuntimeError("offline"))
    )
    result = Router([provider("groq", completion())]).generate(REQUEST, MoneyAnswer, lambda _: True)
    assert result.value.amount_cents == 4200
