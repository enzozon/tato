import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.llm import Attempt, ProviderName


class TechnicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    event: Literal["llm_attempt", "storage_unavailable"]
    provider: ProviderName | None = None
    outcome: str | None = Field(default=None, pattern="^(ok|error|invalid|circuit_open|policy)$")
    input_tokens: int | None = Field(default=None, ge=0, le=1_000_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=1_000_000_000)
    elapsed_ms: int | None = Field(default=None, ge=0, le=86_400_000)

    @classmethod
    def attempt(cls, attempt: Attempt) -> "TechnicalEvent":
        return cls(
            event="llm_attempt",
            provider=attempt.provider,
            outcome=attempt.outcome,
            input_tokens=attempt.input_tokens,
            output_tokens=attempt.output_tokens,
            elapsed_ms=attempt.elapsed_ms,
        )


@dataclass(frozen=True, repr=False)
class Destinations:
    posthog_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    sentry_url: str = ""
    sentry_key: str = ""

    @classmethod
    def configured(cls) -> "Destinations":
        posthog_key = ""
        host = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
        if os.environ.get("POSTHOG_ENABLED") == "true" and host in {
            "https://us.i.posthog.com",
            "https://eu.i.posthog.com",
        }:
            key = os.environ.get("POSTHOG_API_KEY", "")
            if re.fullmatch(r"phc_[A-Za-z0-9_]{10,200}", key):
                posthog_key = key
        sentry_url = sentry_key = ""
        if os.environ.get("SENTRY_ENABLED") == "true":
            dsn = os.environ.get("SENTRY_DSN", "")
            # Aceita somente o contrato Cloud: sem URL arbitrária nem credencial no caminho.
            match = re.fullmatch(
                r"https://([a-f0-9]{32})@(o[0-9]+\.ingest\.(?:us|de)\.sentry\.io)/([0-9]+)",
                dsn,
            )
            if match:
                sentry_key, hostname, project = match.groups()
                sentry_url = f"https://{hostname}/api/{project}/envelope/"
        return cls(posthog_key, host, sentry_url, sentry_key)

    def send(self, client: httpx.Client, event: TechnicalEvent) -> None:
        properties = event.model_dump(exclude_none=True, exclude={"event"})
        if self.posthog_key:
            payload = {
                "api_key": self.posthog_key,
                "event": event.event,
                "distinct_id": "tato-api",
                "properties": {**properties, "$process_person_profile": False, "$ip": None},
            }
            with client.stream(
                "POST",
                self.posthog_host + "/capture/",
                json=payload,
                timeout=1,
                follow_redirects=False,
            ):
                pass
        if self.sentry_url and event.event == "storage_unavailable":
            event_id = uuid4().hex
            packet = {
                "event_id": event_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "platform": "python",
                "level": "error",
                "logger": "tato.technical",
                "message": "storage_unavailable",
            }
            envelope = (
                "\n".join(
                    json.dumps(part) for part in ({"event_id": event_id}, {"type": "event"}, packet)
                )
                + "\n"
            )
            headers = {
                "Content-Type": "application/x-sentry-envelope",
                "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={self.sentry_key}",
            }
            with client.stream(
                "POST",
                self.sentry_url,
                content=envelope.encode(),
                headers=headers,
                timeout=1,
                follow_redirects=False,
            ):
                pass
