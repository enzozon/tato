import httpx
import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from app.llm import Attempt
from app.telemetry import Destinations, TechnicalEvent
from app.telemetry_runtime import Telemetry
from app.telemetry_trace import encode_trace


def test_proto_contains_only_declared_resources_and_attributes(monkeypatch):
    def forbidden_hostname():
        raise AssertionError("Não consultar hostname.")

    monkeypatch.setattr("socket.gethostname", forbidden_hostname)
    for key in (
        "OTEL_RESOURCE_ATTRIBUTES",
        "LOGFIRE_RESOURCE_ATTRIBUTES",
        "LOGFIRE_SERVICE_VERSION",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_SERVICE_NAME",
        "HOSTNAME",
    ):
        monkeypatch.setenv(key, "private-canary")
    monkeypatch.setattr("app.telemetry_trace.time_ns", lambda: 1_000_000_000)
    event = TechnicalEvent.attempt(Attempt("groq", "ok", 0, None, 42))
    payload = encode_trace(event)
    assert b"private-canary" not in payload
    parsed = ExportTraceServiceRequest.FromString(payload)
    resource = parsed.resource_spans[0]
    assert {item.key: item.value.string_value for item in resource.resource.attributes} == {
        "service.name": "tato-api"
    }
    scope = resource.scope_spans[0]
    assert scope.scope.name == "tato.technical"
    span = scope.spans[0]
    assert span.name == "llm_attempt" and span.kind == span.SPAN_KIND_INTERNAL
    assert len(span.trace_id) == 16 and any(span.trace_id)
    assert len(span.span_id) == 8 and any(span.span_id)
    assert not span.parent_span_id and not span.trace_state and not span.events
    assert not span.links and not span.status.message
    assert span.end_time_unix_nano - span.start_time_unix_nano == 42_000_000
    assert {
        item.key: getattr(item.value, item.value.WhichOneof("value")) for item in span.attributes
    } == {
        "provider": "groq",
        "outcome": "ok",
        "input_tokens": 0,
        "elapsed_ms": 42,
    }
    assert encode_trace(event) != payload


@pytest.mark.parametrize("region", ["us", "eu"])
def test_logfire_opt_in_and_explicit_regional_transport(monkeypatch, region):
    monkeypatch.setenv("LOGFIRE_TOKEN", "synthetic_token_for_tests")
    monkeypatch.delenv("LOGFIRE_ENABLED", raising=False)
    assert not Destinations.configured().logfire_token
    monkeypatch.setenv("LOGFIRE_ENABLED", "true")
    monkeypatch.setenv("LOGFIRE_REGION", region)
    destinations = Destinations.configured()
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200)

    event = TechnicalEvent.attempt(Attempt("groq", "ok", 1, 2, 3))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        destinations.send(client, event)
        destinations.send(client, TechnicalEvent(event="storage_unavailable"))
    assert len(requests) == 1
    assert str(requests[0].url) == f"https://logfire-{region}.pydantic.dev/v1/traces"
    assert requests[0].headers["Authorization"] == "synthetic_token_for_tests"
    assert requests[0].headers["Content-Type"] == "application/x-protobuf"
    assert requests[0].extensions["timeout"]["read"] == 1
    assert ExportTraceServiceRequest.FromString(requests[0].content).resource_spans


@pytest.mark.parametrize(
    "token,region",
    [
        ("short", "us"),
        ("synthetic_token_for_tests\n", "us"),
        ("synthetic_token_for_tests", "https://evil.example"),
    ],
)
def test_logfire_untrusted_config_disabled(monkeypatch, token, region):
    monkeypatch.setenv("LOGFIRE_ENABLED", "true")
    monkeypatch.setenv("LOGFIRE_REGION", region)
    monkeypatch.setenv("LOGFIRE_TOKEN", token)
    assert not Destinations.configured().logfire_token


def test_logfire_reuses_existing_queue_sample_and_cap(monkeypatch):
    destinations = Destinations(
        logfire_token="synthetic", logfire_url="https://logfire-us.pydantic.dev/v1/traces"
    )
    telemetry = Telemetry(destinations)
    telemetry.worker = object()
    monkeypatch.setattr("app.telemetry_runtime.random", lambda: 0)
    event = TechnicalEvent.attempt(Attempt("groq", "ok"))
    telemetry.enqueue(event)
    assert telemetry.queue.get_nowait() == event
    telemetry.counts["llm_attempt"] = 1000
    telemetry.enqueue(event)
    assert telemetry.queue.empty()


def test_logfire_failure_does_not_hide_posthog_or_retry():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "logfire-us.pydantic.dev":
            raise httpx.ConnectError("private")
        return httpx.Response(200)

    destinations = Destinations(
        posthog_key="synthetic",
        logfire_token="synthetic",
        logfire_url="https://logfire-us.pydantic.dev/v1/traces",
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        destinations.send(client, TechnicalEvent.attempt(Attempt("groq", "ok")))
    assert len(requests) == 2
    assert requests[-1].url.host == "us.i.posthog.com"
