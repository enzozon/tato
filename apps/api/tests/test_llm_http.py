import json

import httpx
import pytest

from app.llm import Generation, ProviderError
from app.llm_http import HTTPProvider, retry_after


@pytest.mark.parametrize(
    "provider,model",
    [
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
        ("openrouter", "example:free"),
    ],
)
def test_adapters_send_delimited_data_and_measure_tokens(provider, model):
    def handler(request):
        body = json.loads(request.content)
        assert "untrusted_data" in request.content.decode()
        assert "api-secret" not in str(request.url)
        if provider == "gemini":
            assert body["generationConfig"]["responseMimeType"] == "application/json"
            payload = {
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3},
            }
        else:
            if provider == "openrouter":
                assert body["provider"]["data_collection"] == "deny"
            payload = {
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = HTTPProvider(provider, model, "api-secret", client)
        result = adapter.generate(
            Generation(instruction="classifique", data="teste", classification="synthetic"), {}
        )
        assert (result.input_tokens, result.output_tokens) == (12, 3)
        assert "api-secret" not in repr(adapter)
        with pytest.raises(ProviderError, match="personal_data_disabled"):
            adapter.generate(Generation(instruction="x", data="privado"), {})


@pytest.mark.parametrize(
    "status,retryable", [(429, False), (401, False), (503, True), (302, False)]
)
def test_http_failures_never_echo_provider_body(status, retryable):
    def handler(request):
        return httpx.Response(status, text="secret data", headers={"retry-after": "120"})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderError) as error,
    ):
        HTTPProvider("groq", "openai/gpt-oss-20b", "key", client).generate(
            Generation(instruction="x", data="x", classification="public"), {}
        )
    assert error.value.retryable == retryable
    assert error.value.cooldown == 120
    assert "secret" not in str(error.value)


def test_retry_after_is_bounded():
    assert retry_after("garbage") == 60
    assert retry_after("9999999") == 86400
    assert retry_after("Thu, 01 Jan 1970 00:00:00 GMT") == 1


@pytest.mark.parametrize("failure", ["timeout", "large", "truncated", "usage", "json"])
def test_unusable_response_fails_without_private_payload(failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private payload")
        if failure == "large":
            return httpx.Response(200, content=b"x" * 128001)
        if failure == "json":
            return httpx.Response(200, text="private payload")
        payload = {
            "choices": [
                {
                    "finish_reason": "length" if failure == "truncated" else "stop",
                    "message": {"content": "{}"},
                }
            ]
        }
        return httpx.Response(200, json=payload)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderError) as error,
    ):
        HTTPProvider("groq", "openai/gpt-oss-20b", "key", client).generate(
            Generation(instruction="x", data="x", classification="synthetic"), {}
        )
    assert "private" not in str(error.value)


def test_paid_openrouter_model_is_rejected_before_network():
    def handler(request):
        pytest.fail("Modelo pago não pode gerar chamada.")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderError, match="paid_model_blocked"),
    ):
        HTTPProvider("openrouter", "example:paid", "key", client).generate(
            Generation(instruction="x", data="x", classification="synthetic"), {}
        )
