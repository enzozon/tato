import base64
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("web_config", Path("scripts/check_config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def jwt(role):
    return (
        "header." + base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode() + ".sig"
    )


def test_public_configuration_rejects_admin_keys():
    assert config.public_key(jwt("anon"))
    assert not config.public_key(jwt("service_role"))
    assert not config.public_key("sb_secret_private")
    assert not config.safe_url("https://user:secret@example.test")
    assert not config.safe_url("http://example.test", local=True)
    assert config.safe_url("http://127.0.0.1:8000", local=True)


def test_web_export_is_an_allowlist(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "apps/web").mkdir(parents=True)
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", jwt("service_role"))
    with pytest.raises(ValueError):
        config.write_web()
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", jwt("anon"))
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "never-copy-this")
    for name in ("SENTRY_DSN", "POSTHOG_API_KEY", "LOGFIRE_TOKEN"):
        monkeypatch.setenv(name, "never-copy-this")
    config.write_web()
    value = (tmp_path / "apps/web/.env.local").read_text()
    assert "never-copy-this" not in value and "NEXT_PUBLIC_SUPABASE_URL=" in value


@pytest.mark.parametrize(
    "url",
    [
        "https://@example.test",
        "https://example.test:invalid",
        "https://[invalid",
        "https://example.test:0",
        "https://example.test:99999",
        "https://example.test\n",
        " https://example.test",
        "https://exam\tple.test",
    ],
)
def test_public_url_rejects_malformed_or_normalized_values(url):
    assert not config.safe_url(url, local=True)


def test_telemetry_audit_distinguishes_disabled_invalid_and_local_format(monkeypatch):
    names = ("SENTRY", "POSTHOG", "LOGFIRE")
    for name in names:
        monkeypatch.setenv(name + "_ENABLED", "false")
    assert config.audit_telemetry() == dict.fromkeys(names, "desativado")
    for name in names:
        monkeypatch.setenv(name + "_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", "private-invalid-dsn")
    monkeypatch.setenv("POSTHOG_API_KEY", "private-invalid-key")
    monkeypatch.setenv("LOGFIRE_TOKEN", "private\ninvalid-token")
    assert config.audit_telemetry() == dict.fromkeys(names, "pendente ou inválido")
    monkeypatch.setenv("SENTRY_DSN", "https://" + "0" * 32 + "@o1.ingest.us.sentry.io/2")
    monkeypatch.setenv("POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_" + "synthetic" * 3)
    monkeypatch.setenv("LOGFIRE_REGION", "us")
    monkeypatch.setenv("LOGFIRE_TOKEN", "synthetic-write-token")
    assert config.audit_telemetry() == dict.fromkeys(
        names, "formato válido; ensaio remoto pendente"
    )
