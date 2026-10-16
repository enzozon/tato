"""Envia um evento sintético por execução; aceitação HTTP não prova ingestão."""

import argparse
import json
import os
from dataclasses import replace

import httpx

from app.telemetry import Destinations, TechnicalEvent


def probe(service: str) -> dict[str, str | int | None]:
    flag = f"{service.upper()}_ENABLED"
    previous = os.environ.get(flag)
    try:
        os.environ[flag] = "true"
        configured = Destinations.configured()
    finally:
        if previous is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = previous
    destination = Destinations()
    if service == "sentry":
        destination = replace(
            destination, sentry_url=configured.sentry_url, sentry_key=configured.sentry_key
        )
        ready = bool(destination.sentry_url)
    elif service == "posthog":
        destination = replace(
            destination, posthog_key=configured.posthog_key, posthog_host=configured.posthog_host
        )
        ready = bool(destination.posthog_key)
    elif service == "logfire":
        destination = replace(
            destination, logfire_token=configured.logfire_token, logfire_url=configured.logfire_url
        )
        ready = bool(destination.logfire_token)
    else:
        raise ValueError("Serviço não permitido")
    result: dict[str, str | int | None] = {
        "service": service,
        "http_status": None,
        "result": "configuracao_invalida",
    }
    if not ready:
        return result

    def observe(response: httpx.Response) -> None:
        # Não ler corpo/headers: podem conter identificadores ou ecoar credenciais.
        status = response.status_code
        result["http_status"] = status
        if 200 <= status < 300:
            result["result"] = "aceito_http_ingestao_nao_verificada"
        elif status in {401, 403}:
            result["result"] = "credencial_rejeitada"
        elif status == 404:
            result["result"] = "projeto_ou_regiao_nao_encontrado"
        elif status == 429:
            result["result"] = "limite_do_provedor"
        else:
            result["result"] = "resposta_http_inesperada"

    event = (
        TechnicalEvent(event="storage_unavailable")
        if service == "sentry"
        else TechnicalEvent(
            event="llm_attempt",
            provider="groq",
            outcome="ok",
            input_tokens=0,
            output_tokens=0,
            elapsed_ms=0,
        )
    )
    result["result"] = "sem_resposta_http"
    with httpx.Client(trust_env=False, event_hooks={"response": [observe]}) as client:
        destination.send(client, event)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("sentry", "posthog", "logfire"))
    parser.add_argument("--confirm-free-tier", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_free_tier:
        print("Ensaio não executado: confirme o plano gratuito com --confirm-free-tier.")
        return 2
    result = probe(args.service)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["result"] == "aceito_http_ingestao_nao_verificada" else 1


if __name__ == "__main__":
    raise SystemExit(main())
