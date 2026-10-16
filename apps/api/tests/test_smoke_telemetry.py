import importlib.util
import json
import os
from pathlib import Path

import httpx
import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

spec = importlib.util.spec_from_file_location("smoke_telemetry", Path("scripts/smoke_telemetry.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
CLIENT = httpx.Client
FLAGS = ("SENTRY_ENABLED", "POSTHOG_ENABLED", "LOGFIRE_ENABLED")


@pytest.fixture(autouse=True)
def synthetic_configuration(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "false")
    monkeypatch.setenv("SENTRY_DSN", "https://" + "a" * 32 + "@o123.ingest.us.sentry.io/456")
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_" + "b" * 20)
    monkeypatch.setenv("POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setenv("LOGFIRE_TOKEN", "synthetic-logfire-token")
    monkeypatch.setenv("LOGFIRE_REGION", "us")


def mock_client(monkeypatch, handler):
    def create(**kwargs):
        assert kwargs["trust_env"] is False
        return CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(smoke.httpx, "Client", create)


def forbidden_client(**kwargs):
    pytest.fail("Nenhuma conexão deve ser criada")


def test_confirmation_required_before_network(monkeypatch, capsys):
    monkeypatch.setattr(smoke.httpx, "Client", forbidden_client)
    assert smoke.main(["posthog"]) == 2
    assert "--confirm-free-tier" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("service", "name"),
    [("posthog", "POSTHOG_API_KEY"), ("sentry", "SENTRY_DSN"), ("logfire", "LOGFIRE_TOKEN")],
)
def test_invalid_configuration_never_connects(monkeypatch, service, name):
    monkeypatch.setenv(name, "invalid-secret-value")
    if service == "logfire":
        monkeypatch.setenv("LOGFIRE_REGION", "invalid")
    monkeypatch.setattr(smoke.httpx, "Client", forbidden_client)
    assert smoke.probe(service) == {
        "service": service,
        "http_status": None,
        "result": "configuracao_invalida",
    }


@pytest.mark.parametrize("service", ["posthog", "sentry", "logfire"])
@pytest.mark.parametrize("previous", [None, "false", "true"])
def test_single_synthetic_destination_restores_flags(monkeypatch, service, previous):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")
    flag = f"{service.upper()}_ENABLED"
    if previous is None:
        monkeypatch.delenv(flag)
    else:
        monkeypatch.setenv(flag, previous)
    environment = dict(os.environ)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200)

    mock_client(monkeypatch, respond)
    assert smoke.probe(service)["result"] == "aceito_http_ingestao_nao_verificada"
    assert dict(os.environ) == environment
    assert len(requests) == 1
    request = requests[0]
    assert request.extensions["timeout"]["read"] == 1
    if service == "posthog":
        assert request.url.host == "us.i.posthog.com"
        payload = json.loads(request.content)
        assert payload["event"] == "llm_attempt" and payload["distinct_id"] == "tato-api"
        assert payload["properties"] == {
            "provider": "groq",
            "outcome": "ok",
            "input_tokens": 0,
            "output_tokens": 0,
            "elapsed_ms": 0,
            "$process_person_profile": False,
            "$ip": None,
        }
    elif service == "sentry":
        assert request.url.host == "o123.ingest.us.sentry.io"
        payload = [json.loads(line) for line in request.content.decode().splitlines()]
        assert payload[-1]["message"] == "storage_unavailable"
        assert "user" not in payload[-1] and "exception" not in payload[-1]
    else:
        assert request.url.host == "logfire-us.pydantic.dev"
        trace = ExportTraceServiceRequest.FromString(request.content)
        span = trace.resource_spans[0].scope_spans[0].spans[0]
        assert span.name == "llm_attempt"
        assert {attribute.key for attribute in span.attributes} == {
            "provider",
            "outcome",
            "input_tokens",
            "output_tokens",
            "elapsed_ms",
        }


@pytest.mark.parametrize(
    ("status", "result"),
    [
        (200, "aceito_http_ingestao_nao_verificada"),
        (202, "aceito_http_ingestao_nao_verificada"),
        (301, "resposta_http_inesperada"),
        (401, "credencial_rejeitada"),
        (403, "credencial_rejeitada"),
        (404, "projeto_ou_regiao_nao_encontrado"),
        (429, "limite_do_provedor"),
        (500, "resposta_http_inesperada"),
    ],
)
def test_http_result_is_sanitized_without_retry(monkeypatch, capsys, status, result):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status,
            text="private-secret-response",
            headers={"Location": "https://private-secret.example"},
        )

    mock_client(monkeypatch, respond)
    expected_exit = 0 if 200 <= status < 300 else 1
    assert smoke.main(["posthog", "--confirm-free-tier"]) == expected_exit
    assert json.loads(capsys.readouterr().out) == {
        "service": "posthog",
        "http_status": status,
        "result": result,
    }
    assert len(requests) == 1


def test_timeout_has_no_retry_or_raw_error(monkeypatch, capsys):
    requests = []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout("secret-key-and-private-url", request=request)

    mock_client(monkeypatch, timeout)
    assert smoke.main(["logfire", "--confirm-free-tier"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "service": "logfire",
        "http_status": None,
        "result": "sem_resposta_http",
    }
    assert len(requests) == 1


def test_response_body_is_never_read(monkeypatch):
    class Unreadable(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("O ensaio HTTP não deve ler corpos remotos")
            yield b""

    mock_client(monkeypatch, lambda request: httpx.Response(200, stream=Unreadable()))
    assert smoke.probe("posthog")["result"] == "aceito_http_ingestao_nao_verificada"


def test_flag_restored_when_configuration_fails(monkeypatch):
    monkeypatch.delenv("SENTRY_ENABLED")

    def broken():
        raise RuntimeError("synthetic")

    monkeypatch.setattr(smoke.Destinations, "configured", broken)
    with pytest.raises(RuntimeError, match="synthetic"):
        smoke.probe("sentry")
    assert "SENTRY_ENABLED" not in os.environ
