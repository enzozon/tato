import json

import httpx
import pytest
from pydantic import ValidationError

from app.llm import Attempt
from app.telemetry import Destinations, TechnicalEvent


def test_disabled_without_explicit_flags(monkeypatch):
    monkeypatch.delenv("POSTHOG_ENABLED", raising=False)
    monkeypatch.delenv("SENTRY_ENABLED", raising=False)
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_" + "a" * 20)
    monkeypatch.setenv("SENTRY_DSN", "https://" + "a" * 32 + "@o123.ingest.us.sentry.io/456")
    destinations = Destinations.configured()
    assert not destinations.posthog_key and not destinations.sentry_url


@pytest.mark.parametrize(
    "dsn",
    [
        "http://" + "a" * 32 + "@o1.ingest.us.sentry.io/2",
        "https://" + "a" * 32 + "@evil.example/2",
        "https://" + "a" * 32 + "@o1.ingest.us.sentry.io/2?secret=x",
        "https://" + "a" * 32 + "@o1.ingest.us.sentry.io:443/2",
        "https://" + "a" * 32 + "@o1.ingest.us.sentry.io/2\n",
    ],
)
def test_untrusted_sentry_destinations_disabled(monkeypatch, dsn):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", dsn)
    assert not Destinations.configured().sentry_url


def test_payload_allowlist_without_private_context(monkeypatch):
    monkeypatch.setenv("POSTHOG_ENABLED", "true")
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_" + "a" * 20)
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", "https://" + "b" * 32 + "@o1.ingest.de.sentry.io/2")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        destinations = Destinations.configured()
        destinations.send(client, TechnicalEvent.attempt(Attempt("groq", "ok", 0, None, 25)))
        destinations.send(client, TechnicalEvent(event="storage_unavailable"))
    assert len(requests) == 3
    assert requests[0].url.path == "/i/v0/e/"
    llm = json.loads(requests[0].content)
    assert llm == {
        "api_key": "phc_" + "a" * 20,
        "event": "llm_attempt",
        "distinct_id": "tato-api",
        "properties": {
            "provider": "groq",
            "outcome": "ok",
            "input_tokens": 0,
            "elapsed_ms": 25,
            "$process_person_profile": False,
            "$ip": None,
        },
    }
    sentry = [json.loads(line) for line in requests[-1].content.decode().splitlines()]
    assert set(sentry[2]) == {"event_id", "timestamp", "platform", "level", "logger", "message"}
    assert sentry[2]["message"] == "storage_unavailable"
    assert requests[-1].url.host == "o1.ingest.de.sentry.io"
    for request in requests:
        assert "authorization" not in request.headers
        assert request.extensions["timeout"]["read"] == 1


def test_posthog_unknown_host_and_key_disabled(monkeypatch):
    monkeypatch.setenv("POSTHOG_ENABLED", "true")
    monkeypatch.setenv("POSTHOG_HOST", "https://evil.example")
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_" + "a" * 20)
    assert not Destinations.configured().posthog_key
    monkeypatch.setenv("POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setenv("POSTHOG_API_KEY", "personal_token")
    assert not Destinations.configured().posthog_key


@pytest.mark.parametrize(
    "extra",
    [
        {"prompt": "private"},
        {"user_id": "private"},
        {"exception": "private"},
        {"provider": "private"},
        {"outcome": "private"},
        {"elapsed_ms": True},
        {"input_tokens": -1},
        {"output_tokens": 1_000_000_001},
    ],
)
def test_event_rejects_nontechnical_fields(extra):
    with pytest.raises(ValidationError):
        TechnicalEvent(event="llm_attempt", **extra)


def test_repr_never_includes_credentials():
    assert "secret" not in repr(Destinations(posthog_key="secret", sentry_key="secret"))


def test_legacy_cloud_dsn_remains_valid(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", "https://" + "a" * 32 + "@o1.ingest.sentry.io/2")
    assert Destinations.configured().sentry_url == "https://o1.ingest.sentry.io/api/2/envelope/"
