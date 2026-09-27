"""Ensaio opt-in com valores sintéticos; imprime somente métricas de uso."""

import json
from dataclasses import asdict

from app.llm import Generation, LLMUnavailable, MoneyAnswer, verify_money
from app.llm_service import runtime_router


def main() -> None:
    request = Generation(
        instruction="Retorne source_id=demo e amount_cents=4200 no JSON solicitado.",
        data="Exemplo sintético de total calculado: 4200 centavos; fonte demo.",
        classification="synthetic",
    )
    try:
        result = runtime_router().generate(
            request, MoneyAnswer, lambda value: verify_money(value, {"demo": 4200})
        )
    except LLMUnavailable as error:
        print(json.dumps({"ok": False, "attempts": [asdict(a) for a in error.attempts]}))
        raise SystemExit(
            "LLM indisponível; confira habilitação, plano gratuito e chaves."
        ) from None
    print(json.dumps({"ok": True, "attempts": [asdict(a) for a in result.attempts]}))


if __name__ == "__main__":
    main()
