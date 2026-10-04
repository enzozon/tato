from unittest.mock import Mock

import httpx
import pytest

from app.llm import Completion, Generation, LLMUnavailable, MoneyAnswer, ProviderError
from app.llm_http import HTTPProvider
from app.llm_policy import personal_allowed
from app.llm_router import Router

FLAGS = [
    "LLM_ENABLED",
    "LLM_FREE_TIER_CONFIRMED",
    "GROQ_PERSONAL_DATA_ENABLED",
    "GROQ_ZDR_CONFIRMED",
]


def test_every_gate_is_required_and_other_providers_stay_blocked(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    assert personal_allowed("groq")
    assert not personal_allowed("gemini") and not personal_allowed("openrouter")
    for flag in FLAGS:
        monkeypatch.setenv(flag, "false")
        assert not personal_allowed("groq")
        monkeypatch.setenv(flag, "true")


def test_personal_failure_never_falls_back_to_other_providers(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    providers = []
    for name in ["groq", "gemini", "openrouter"]:
        provider = Mock(name=name)
        provider.name, provider.model = name, "test"
        provider.generate.side_effect = ProviderError("http_429")
        providers.append(provider)
    request = Generation(instruction="teste", data="sintético", classification="personal")
    with pytest.raises(LLMUnavailable) as error:
        Router(providers).generate(request, MoneyAnswer, lambda _: True)
    providers[0].generate.assert_called_once()
    for provider in providers[1:]:
        provider.generate.assert_not_called()
    assert [attempt.outcome for attempt in error.value.attempts] == ["error", "policy", "policy"]


def test_adapter_enforces_policy_even_when_called_directly(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    request = Generation(instruction="teste", data="sintético", classification="personal")
    client = Mock(spec=httpx.Client)
    for name, model in [("gemini", "gemini-2.5-flash"), ("openrouter", "test:free")]:
        with pytest.raises(ProviderError, match="personal_data_disabled"):
            HTTPProvider(name, model, "synthetic-key", client).generate(request, {})
    client.stream.assert_not_called()


def test_personal_request_uses_groq_when_authorized(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    provider = Mock()
    provider.name, provider.model = "groq", "test"
    provider.generate.return_value = Completion(
        content='{"source_id":"test","amount_cents":42}', input_tokens=1, output_tokens=1
    )
    result = Router([provider]).generate(
        Generation(instruction="teste", data="sintético"), MoneyAnswer, lambda _: True
    )
    assert result.value.amount_cents == 42
