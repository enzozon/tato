from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from queue import Full, Queue
from random import random
from threading import Lock, Thread

import httpx

from app.llm import Attempt
from app.telemetry import Destinations, TechnicalEvent


class Telemetry:
    def __init__(self, destinations: Destinations):
        self.destinations = destinations
        self.queue: Queue[TechnicalEvent] = Queue(maxsize=32)
        self.lock = Lock()
        self.month = datetime.now(UTC).strftime("%Y-%m")
        self.counts: Counter[str] = Counter()
        self.worker: Thread | None = None

    def enqueue(self, event: TechnicalEvent) -> None:
        if not (
            self.destinations.posthog_key
            or self.destinations.sentry_url
            or self.destinations.logfire_token
        ):
            return
        if event.event == "llm_attempt" and (
            not (self.destinations.posthog_key or self.destinations.logfire_token)
            or random() >= 0.1
        ):
            return
        with self.lock:
            month = datetime.now(UTC).strftime("%Y-%m")
            if month != self.month:
                self.month = month
                self.counts.clear()
            # shortcut: cota por processo reinicia com ele; plano Free limita a conta.
            if self.counts[event.event] >= 1000:
                return
            try:
                self.queue.put_nowait(event)
            except Full:
                return
            self.counts[event.event] += 1
            if self.worker is None:
                self.worker = Thread(target=self.run, name="tato-telemetry", daemon=True)
                self.worker.start()

    def run(self) -> None:
        with httpx.Client(trust_env=False) as client:
            while True:
                event = self.queue.get()
                try:
                    with suppress(Exception):
                        self.destinations.send(client, event)
                finally:
                    self.queue.task_done()


_configured: Telemetry | None = None
_configuration_lock = Lock()


def configured() -> Telemetry:
    global _configured
    with _configuration_lock:
        if _configured is None:
            _configured = Telemetry(Destinations.configured())
        return _configured


def record_attempt(attempt: Attempt) -> None:
    with suppress(Exception):
        configured().enqueue(TechnicalEvent.attempt(attempt))


def record_storage_failure() -> None:
    with suppress(Exception):
        configured().enqueue(TechnicalEvent(event="storage_unavailable"))
