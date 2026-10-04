import importlib.util
import io
from pathlib import Path
from uuid import uuid4

import pytest

spec = importlib.util.spec_from_file_location("agents_cron", Path("scripts/run_agents.py"))
cron = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cron)


def test_cron_sends_deduplicated_batch_without_redirects(monkeypatch):
    owner = str(uuid4())
    monkeypatch.setenv("TATO_API_URL", "https://example.test")
    monkeypatch.setenv("AGENTS_RUN_TOKEN", "x" * 32)
    monkeypatch.setenv("AGENT_USER_IDS", f'["{owner}", "{owner}"]')

    class Opener:
        def open(self, request, timeout):
            assert timeout == 240
            assert request.full_url == "https://example.test/internal/agents/run"
            assert request.data.count(owner.encode()) == 1
            return io.BytesIO(b'{"processed":1,"inserted":2,"sent":0}')

    monkeypatch.setattr(cron, "build_opener", lambda *args: Opener())
    assert cron.run() == {"processed": 1, "inserted": 2, "sent": 0}
    with pytest.raises(ValueError):
        cron.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test",
        "https://u:p@example.test",
        "https://example.test?secret=x",
        "https://example.test#x",
    ],
)
def test_cron_rejects_unsafe_urls(monkeypatch, url):
    monkeypatch.setenv("TATO_API_URL", url)
    with pytest.raises(ValueError):
        cron.run()
