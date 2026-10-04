"""Avalia somente perguntas sintéticas versionadas, sem banco ou dados do usuário."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from time import sleep
from unittest.mock import patch
from uuid import UUID

from app.chat_intent import classify
from app.chat_language import SmallTalk, conversation, safe_smalltalk
from app.llm import LLMUnavailable
from app.llm_service import runtime_router


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interval", type=int, default=30, choices=range(20, 61))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dataset = root / "evals/chat.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    router = runtime_router()
    if not router.providers:
        raise SystemExit("Avaliação incompleta: provedor não habilitado.")
    fingerprint = hashlib.sha256(dataset.read_bytes())
    for name in ["chat_intent.py", "chat_language.py", "llm_http.py"]:
        fingerprint.update((root / "apps/api/app" / name).read_bytes())
    fingerprint.update((root / "packages/mascot/identity.json").read_bytes())
    fingerprint.update(json.dumps([(p.name, p.model) for p in router.providers]).encode())
    output = root / "test-results/chat-eval.json"
    output.parent.mkdir(exist_ok=True)
    report = {"fingerprint": fingerprint.hexdigest(), "status": "incomplete", "cases": []}
    if args.resume and output.exists():
        report = json.loads(output.read_text(encoding="utf-8"))
        if report["fingerprint"] != fingerprint.hexdigest():
            raise SystemExit("Código/modelo/dataset mudou; execute sem --resume.")
    done = {item["id"] for item in report["cases"]}
    for case in cases:
        if case["id"] in done:
            continue
        attempts, unavailable = [], []

        def generate(
            engine, owner, request, schema, guard, attempts=attempts, unavailable=unavailable
        ):
            if report["cases"]:
                sleep(args.interval)
            try:
                result = router.generate(request, schema, guard)
                attempts.extend(a.__dict__ for a in result.attempts)
                return result
            except LLMUnavailable as error:
                attempts.extend(a.__dict__ for a in error.attempts)
                unavailable.append(True)
                raise

        owner = UUID(int=1)
        with (
            patch("app.chat_intent.generate", generate),
            patch("app.chat_language.generate", generate),
        ):
            if case.get("mode") == "smalltalk":
                value = conversation(None, owner, case["question"], [])
                passed = safe_smalltalk(SmallTalk(message=value)) and not unavailable
                observed = {"message": value}
            else:
                value = classify(None, owner, case["question"], date(2026, 10, 4), []).choice
                observed = value.model_dump(mode="json")
                passed = all(observed.get(k) == v for k, v in case["expected"].items())
                passed = passed and not unavailable
        report["cases"].append(
            {"id": case["id"], "passed": passed, "observed": observed, "attempts": attempts}
        )
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"id": case["id"], "passed": passed}), flush=True)
    report["status"] = "complete"
    report["passed"] = sum(item["passed"] for item in report["cases"])
    report["total"] = len(cases)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["passed"] != len(cases):
        raise SystemExit("Avaliação concluída com falhas; consulte test-results/chat-eval.json.")


if __name__ == "__main__":
    main()
