import hashlib
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.llm import LLMUnavailable
from app.rag.faithfulness import Judgment


def test_judge_resumes_without_repeating_completed_cases(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    main = runpy.run_path(str(root / "scripts/eval_rag_judge.py"))["main"]
    namespace = main.__globals__
    monkeypatch.setitem(namespace, "__file__", str(tmp_path / "scripts/eval_rag_judge.py"))
    monkeypatch.setattr(sys, "argv", ["eval_rag_judge.py"])
    monkeypatch.setitem(namespace, "sleep", lambda _: None)
    provider = SimpleNamespace(name="groq", model="test-only")
    monkeypatch.setitem(namespace, "runtime_router", lambda: SimpleNamespace(providers=[provider]))
    for relative in (
        "knowledge/base.jsonl",
        "apps/api/app/rag/faithfulness.py",
        "apps/api/app/llm_http.py",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic", encoding="utf-8")
    golden = [{"id": str(i), "question": str(i), "expected": "synthetic"} for i in range(40)]
    golden_path = tmp_path / "evals/golden.jsonl"
    golden_path.parent.mkdir()
    golden_path.write_text("\n".join(map(json.dumps, golden)), encoding="utf-8")
    retrieval = {"cases": [{"id": str(i), "hits": []} for i in range(40)]}
    for name, relative in [("corpus", "knowledge/base.jsonl"), ("golden", "evals/golden.jsonl")]:
        retrieval[f"{name}_sha256"] = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
    output = tmp_path / "test-results"
    output.mkdir()
    (output / "rag-eval.json").write_text(json.dumps(retrieval), encoding="utf-8")
    calls = []

    def judge(router, question, expected, hits):
        calls.append(question)
        if len(calls) == 3:
            raise LLMUnavailable("quota")
        return Judgment(supported=[True], answers_question=True), 10, 5

    monkeypatch.setitem(namespace, "evaluate_public", judge)
    with pytest.raises(SystemExit, match="incompleto"):
        main()
    partial = json.loads((output / "rag-judge.json").read_text())
    assert partial["status"] == "incomplete" and len(partial["cases"]) == 2
    monkeypatch.setattr(sys, "argv", ["eval_rag_judge.py", "--resume"])
    main()
    report = json.loads((output / "rag-judge.json").read_text())
    assert report["status"] == "measured" and len(report["cases"]) == 40
    assert calls.count("0") == calls.count("1") == 1
    assert report["faithfulness"] == report["answer_rate"] == 1
    (tmp_path / "apps/api/app/rag/faithfulness.py").write_text("changed")
    with pytest.raises(SystemExit, match="incompleto"):
        main()
    assert len(calls) == 41
