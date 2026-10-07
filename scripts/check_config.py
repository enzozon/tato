"""Audita somente presença/formato; nunca imprime valores de configuração."""

import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def public_key(value: str) -> bool:
    if value.startswith("sb_publishable_") and len(value) > 20:
        return True
    try:
        payload = value.split(".")[1]
        return (
            json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["role"]
            == "anon"
        )
    except (IndexError, ValueError, KeyError, TypeError):
        return False


def safe_url(value: str, *, local: bool = False) -> bool:
    parsed = urlsplit(value)
    return bool(
        parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and (
            parsed.scheme == "https"
            or (local and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})
        )
    )


def audit() -> dict[str, bool]:
    names = [
        "DATABASE_URL",
        "DATA_ENCRYPTION_KEY",
        "DEDUP_HMAC_KEY",
        "SUPABASE_SECRET_KEY",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "RESEND_API_KEY",
        "RESEND_FROM",
    ]
    result = {name: bool(os.environ.get(name)) for name in names}
    result["SUPABASE_URL"] = safe_url(os.environ.get("SUPABASE_URL", ""))
    result["SUPABASE_PUBLISHABLE_KEY"] = public_key(os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""))
    result["AGENTS_RUN_TOKEN"] = len(os.environ.get("AGENTS_RUN_TOKEN", "")) >= 32
    return result


def write_web() -> None:
    config = audit()
    api = os.environ.get("WEB_API_URL", "http://127.0.0.1:8000")
    if not (
        config["SUPABASE_URL"] and config["SUPABASE_PUBLISHABLE_KEY"] and safe_url(api, local=True)
    ):
        raise ValueError("URL ou chave publicável ausente/inválida; arquivo web não alterado.")
    # Seleção explícita impede copiar segredos administrativos do ambiente inteiro.
    values = {
        "NEXT_PUBLIC_API_URL": api,
        "NEXT_PUBLIC_SUPABASE_URL": os.environ["SUPABASE_URL"],
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": os.environ["SUPABASE_PUBLISHABLE_KEY"],
    }
    path = Path("apps/web/.env.local")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if line.split("=", 1)[0] not in values]
    lines.extend(f"{key}={json.dumps(value)}" for key, value in values.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-web", action="store_true")
    args = parser.parse_args()
    for name, ready in audit().items():
        print(f"{name}: {'configurado' if ready else 'pendente ou inválido'}")
    if args.write_web:
        try:
            write_web()
            print("Configuração pública atualizada; valores não exibidos.")
        except ValueError as error:
            raise SystemExit(str(error)) from None
