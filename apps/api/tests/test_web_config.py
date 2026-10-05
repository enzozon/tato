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
    config.write_web()
    value = (tmp_path / "apps/web/.env.local").read_text()
    assert "never-copy-this" not in value and "NEXT_PUBLIC_SUPABASE_URL=" in value
