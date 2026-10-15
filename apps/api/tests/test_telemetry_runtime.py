from threading import Event

import httpx
import pytest

from app.llm import Attempt
from app.telemetry import Destinations, TechnicalEvent
from app.telemetry_runtime import Telemetry, record_attempt, record_storage_failure


def idle(monkeypatch, *, posthog=True):
    telemetry = Telemetry(Destinations(posthog_key="key" if posthog else "", sentry_url="url"))
    telemetry.worker = object()
    monkeypatch.setattr("app.telemetry_runtime.random", lambda: 0)
    return telemetry


def test_disabled_and_sampling_do_not_enqueue(monkeypatch):
    telemetry = Telemetry(Destinations())
    telemetry.enqueue(TechnicalEvent(event="storage_unavailable"))
    assert telemetry.queue.empty() and telemetry.worker is None
    telemetry = idle(monkeypatch)
    monkeypatch.setattr("app.telemetry_runtime.random", lambda: 0.9)
    telemetry.enqueue(TechnicalEvent.attempt(Attempt("groq", "ok")))
    assert telemetry.queue.empty()
    telemetry = idle(monkeypatch, posthog=False)
    telemetry.enqueue(TechnicalEvent.attempt(Attempt("groq", "ok")))
    assert telemetry.queue.empty()


def test_bounded_queue_and_independent_budgets(monkeypatch):
    telemetry = idle(monkeypatch)
    for _ in range(33):
        telemetry.enqueue(TechnicalEvent(event="storage_unavailable"))
    assert telemetry.queue.qsize() == 32
    assert telemetry.counts["storage_unavailable"] == 32
    while not telemetry.queue.empty():
        telemetry.queue.get_nowait()
    telemetry.counts["llm_attempt"] = 1000
    telemetry.enqueue(TechnicalEvent.attempt(Attempt("groq", "ok")))
    telemetry.enqueue(TechnicalEvent(event="storage_unavailable"))
    assert telemetry.queue.qsize() == 1
    telemetry.counts["storage_unavailable"] = 1000
    telemetry.enqueue(TechnicalEvent(event="storage_unavailable"))
    assert telemetry.queue.qsize() == 1
    telemetry.month = "2000-01"
    telemetry.enqueue(TechnicalEvent.attempt(Attempt("groq", "ok")))
    assert telemetry.counts == {"llm_attempt": 1}


@pytest.mark.parametrize("fail", [False, True])
def test_worker_sends_off_thread_without_retry(monkeypatch, fail):
    completed = Event()
    requests = []

    def respond(request):
        requests.append(request)
        completed.set()
        if fail:
            raise httpx.ConnectError("private remote failure")
        return httpx.Response(302, headers={"Location": "https://evil.example"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("app.telemetry_runtime.httpx.Client", lambda **kwargs: client)
    telemetry = Telemetry(Destinations(posthog_key="synthetic"))
    telemetry.enqueue(TechnicalEvent(event="storage_unavailable"))
    assert completed.wait(2)
    assert len(requests) == 1
    assert telemetry.worker.daemon


def test_no_failure_or_invalid_metric_escapes_business(monkeypatch):
    def broken():
        raise RuntimeError("private")

    monkeypatch.setattr("app.telemetry_runtime.configured", broken)
    record_storage_failure()
    record_attempt(Attempt("groq", "ok"))
    telemetry = idle(monkeypatch)
    monkeypatch.setattr("app.telemetry_runtime.configured", lambda: telemetry)
    record_attempt(Attempt("groq", "ok", -1))
    assert telemetry.queue.empty()


def test_posthog_failure_still_attempts_sentry():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "us.i.posthog.com":
            raise httpx.ReadTimeout("private")
        return httpx.Response(429)

    destinations = Destinations(
        "synthetic", sentry_url="https://o1.ingest.us.sentry.io/api/2/envelope/"
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        destinations.send(client, TechnicalEvent(event="storage_unavailable"))
    assert len(requests) == 2


def test_storage_hook_receives_no_request_or_exception(monkeypatch):
    import asyncio
    from unittest.mock import Mock

    from app.main import storage_unavailable

    capture = Mock()
    monkeypatch.setattr("app.main.record_storage_failure", capture)
    response = asyncio.run(storage_unavailable(Mock(), RuntimeError("private raw exception")))
    assert response.status_code == 503
    assert b"private" not in response.body
    capture.assert_called_once_with()


def test_lazy_configuration_is_single_instance_under_concurrency(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from app.telemetry_runtime import configured

    monkeypatch.setattr("app.telemetry_runtime._configured", None)
    monkeypatch.setattr(Destinations, "configured", lambda: Destinations())
    with ThreadPoolExecutor(max_workers=8) as pool:
        instances = list(pool.map(lambda _: configured(), range(24)))
    assert all(instance is instances[0] for instance in instances)
