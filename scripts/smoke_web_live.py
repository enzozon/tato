"""Ensaio opt-in: identidade sintética Supabase, Upstash real e banco local novo."""

import argparse
import json
import os
import re
import secrets
import subprocess
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.account_service import request_deletion
from app.auth import Identity, service_key, service_url
from app.database import app_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-free-tier", action="store_true", required=True)
    parser.parse_args()
    for name in ["DATABASE_URL", "DATABASE_MIGRATION_URL"]:
        url = make_url(os.environ[name])
        if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").startswith(
            "tato_dev_"
        ):
            raise ValueError("Ensaio exige banco local tato_dev_; banco antigo não é permitido.")
    base = service_url("SUPABASE_URL")
    if not httpx.URL(base).host.endswith(".supabase.co"):
        raise ValueError("Use o domínio oficial do projeto Supabase.")
    key = service_key("SUPABASE_SECRET_KEY")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    owner: UUID | None = None
    email = f"tato-smoke-{secrets.token_hex(12)}@example.test"
    password = secrets.token_urlsafe(36)
    runtime = app_engine(os.environ["DATABASE_URL"])
    admin = app_engine(os.environ["DATABASE_MIGRATION_URL"])
    state = Path("test-results/live-smoke-owner.json")
    if state.exists():
        raise ValueError("Há um ensaio anterior sem limpeza confirmada; confira o registro local.")
    os.environ["RATE_LIMIT_BACKEND"] = "upstash"
    for engine in [runtime, admin]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        try:
            response = client.post(
                f"{base}/auth/v1/admin/users",
                headers=headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            response.raise_for_status()
            owner = UUID(response.json()["id"])
            state.parent.mkdir(exist_ok=True)
            state.write_text(json.dumps({"owner": str(owner)}), encoding="utf-8")
            environment = {
                **os.environ,
                "TATO_LIVE_WEB": "true",
                "TATO_SMOKE_EMAIL": email,
                "TATO_SMOKE_PASSWORD": password,
            }
            result = subprocess.run(
                [
                    "npm.cmd" if os.name == "nt" else "npm",
                    "exec",
                    "--workspace=tato-web",
                    "--",
                    "playwright",
                    "test",
                    "--config=playwright.integration.config.ts",
                ],
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
            )
            # Saída bruta pode conter entradas dos formulários em falhas do navegador.
            stages = re.findall(r"LIVE_STAGE=([a-z_]+)", result.stdout)
            print("Etapas concluídas: " + ", ".join(stages))
            if result.returncode:
                raise ValueError("Fluxo remoto não aprovado; saída com credenciais suprimida.")
            response = client.get(f"{base}/auth/v1/admin/users/{owner}", headers=headers)
            if response.status_code != 404:
                raise ValueError("Exclusão no Supabase não confirmada.")
            with admin.connect() as connection:
                count = connection.execute(
                    text("SELECT count(*) FROM users WHERE id=:owner"), {"owner": owner}
                ).scalar_one()
            if count:
                raise ValueError("Exclusão local não confirmada.")
            print("Login, ledger, Upstash e exclusão real aprovados; conta temporária removida.")
        finally:
            if owner is not None:
                # Remove somente a identidade criada nesta execução, inclusive após falha.
                with admin.connect() as connection:
                    exists = connection.execute(
                        text("SELECT count(*) FROM users WHERE id=:owner"), {"owner": owner}
                    ).scalar_one()
                if exists:
                    request_deletion(runtime, owner, lambda: Identity(id=owner))
                response = client.request(
                    "DELETE",
                    f"{base}/auth/v1/admin/users/{owner}",
                    headers=headers,
                    json={"should_soft_delete": False},
                )
                if response.status_code not in {200, 204, 404}:
                    raise ValueError("Limpeza remota pendente; identidade no registro local.")
                state.unlink(missing_ok=True)
            runtime.dispose()
            admin.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Ensaio não aprovado: {type(error).__name__}.") from None
