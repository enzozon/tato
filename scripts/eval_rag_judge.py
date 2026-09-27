"""Avaliação opt-in de respostas públicas; ausência de provedor é falha, não skip."""

import hashlib
import json
from pathlib import Path

from app.llm import LLMUnavailable
from app.llm_service import runtime_router
from app.rag.faithfulness import evaluate_public
from app.rag.retrieval import Hit


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "test-results/rag-judge.json"
    output.parent.mkdir(exist_ok=True)
    report = {"status": "incomplete", "cases": []}
    output.write_text(json.dumps(report), encoding="utf-8")
    try:
        router = runtime_router()
        if not router.providers:
            raise LLMUnavailable("Nenhum provedor habilitado.")
        retrieval = json.loads((root / "test-results/rag-eval.json").read_text(encoding="utf-8"))
        for name, relative in [
            ("corpus", "knowledge/base.jsonl"),
            ("golden", "evals/golden.jsonl"),
        ]:
            if (
                hashlib.sha256((root / relative).read_bytes()).hexdigest()
                != retrieval[f"{name}_sha256"]
            ):
                raise ValueError("Execute rag-eval novamente: dados foram alterados.")
        golden = {
            item["id"]: item
            for item in map(
                json.loads, (root / "evals/golden.jsonl").read_text(encoding="utf-8").splitlines()
            )
        }
        if len(retrieval["cases"]) != 40 or {c["id"] for c in retrieval["cases"]} != set(golden):
            raise ValueError("Relatório de recuperação incompleto.")
        for case in retrieval["cases"]:
            item = golden[case["id"]]
            result, input_tokens, output_tokens = evaluate_public(
                router,
                item["question"],
                item["expected"],
                [Hit.model_validate(hit) for hit in case["hits"]],
            )
            report["cases"].append(
                {
                    "id": case["id"],
                    **result.model_dump(),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            )
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        claims = [supported for case in report["cases"] for supported in case["supported"]]
        report.update(
            {
                "status": "measured",
                "faithfulness": sum(claims) / len(claims) if claims else None,
                "answer_rate": sum(c["answers_question"] for c in report["cases"]) / 40,
                "corpus_sha256": retrieval["corpus_sha256"],
                "golden_sha256": retrieval["golden_sha256"],
                "providers": [{"name": p.name, "model": p.model} for p in router.providers],
            }
        )
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "cases"}))
        if not claims:
            raise ValueError("Sem afirmações para avaliar.")
    except (LLMUnavailable, ValueError, OSError, KeyError):
        raise SystemExit(
            "Judge incompleto; confira relatório, dados, configuração e quota."
        ) from None


if __name__ == "__main__":
    main()
