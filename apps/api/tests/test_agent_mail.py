from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app import agent_mail as mail
from app.models import Insight


@pytest.fixture
def enabled(monkeypatch):
    for name, value in {
        "AGENT_EMAIL_ENABLED": "true",
        "RESEND_FREE_TIER_CONFIRMED": "true",
        "SUPABASE_URL": "https://synthetic.supabase.co",
        "SUPABASE_SECRET_KEY": "fake",
        "RESEND_API_KEY": "fake",
        "RESEND_FROM": "test@example.com",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    "confirmed,matching,send_status,expected",
    [
        (True, True, 200, True),
        (False, True, 200, False),
        (True, False, 200, False),
        (True, True, 429, False),
        (True, True, 500, False),
    ],
)
def test_only_verified_owner_receives_generic_notice(
    enabled, monkeypatch, confirmed, matching, send_status, expected
):
    owner, insight = uuid4(), uuid4()

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": str(owner if matching else uuid4()),
                    "email": "verified@example.com",
                    "email_confirmed_at": "2026-01-01T00:00:00Z" if confirmed else None,
                },
            )
        assert request.url == "https://api.resend.com/emails"
        assert request.headers["Idempotency-Key"] == f"agent-notice/{insight}"
        assert str(owner) not in request.content.decode()
        assert "saldo" not in request.content.decode()
        return httpx.Response(send_status, json={"id": str(uuid4())})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(mail.httpx, "Client", lambda **kwargs: client)
    assert mail.send_notice(owner, insight) == expected


def test_disabled_email_never_calls_network(monkeypatch):
    monkeypatch.delenv("AGENT_EMAIL_ENABLED", raising=False)
    monkeypatch.setattr(mail.httpx, "Client", lambda **kw: pytest.fail("Envio desabilitado"))
    assert not mail.send_notice(uuid4(), uuid4())
    assert mail.deliver_pending(None, uuid4()) == 0


def test_retry_window_is_bounded_by_provider_idempotency():
    now = datetime.now(UTC)
    row = Insight(
        user_id=uuid4(),
        agent_kind="goal",
        event_key="synthetic",
        content_ciphertext=b"synthetic",
        email_status="pending",
        created_at=now,
    )
    assert mail.eligible(row, now)
    row.email_attempts, row.email_last_attempt_at = 1, now
    assert not mail.eligible(row, now + timedelta(seconds=30))
    assert mail.eligible(row, now + timedelta(minutes=3))
    assert not mail.eligible(row, now + timedelta(hours=24))
    row.email_attempts = 3
    assert not mail.eligible(row, now + timedelta(minutes=3))
