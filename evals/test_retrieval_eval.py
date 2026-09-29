import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter

import pytest
from sqlalchemy import delete
from sqlmodel import col

from app.database import tenant_session
from app.models import KnowledgeChunk
from app.rag.embedding import embed, encoder
from app.rag.indexing import index_public
from app.rag.ranking import retrieval_metrics
from app.rag.reranking import rerank
from app.rag.retrieval import search

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.eval
def test_real_hybrid_retrieval(admin_engine, runtime_engine, owners):
    corpus_path = ROOT / "knowledge/base.jsonl"
    golden_path = ROOT / "evals/golden.jsonl"
    corpus = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()]
    golden = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines()]
    slugs = {item["slug"] for item in corpus}
    assert len(golden) == len({item["id"] for item in golden}) == 40
    assert all(set(item["relevant"]) <= slugs and item["expected"] for item in golden)
    started = perf_counter()
    raw, reranked, cases = [], [], []
    try:
        for item in corpus:
            index_public(admin_engine, item["slug"], f"# {item['title']}\n\n{item['text']}")
        indexed_seconds = perf_counter() - started
        model = encoder()[2]
        vectors = embed([item["question"] for item in golden], query=True)
        search_seconds = rerank_seconds = 0.0
        for item, vector in zip(golden, vectors, strict=True):
            started = perf_counter()
            with tenant_session(runtime_engine, owners[0]) as session:
                hits = search(session, owners[0], item["question"], vector, model, b"e" * 32)
            search_seconds += perf_counter() - started
            started = perf_counter()
            refined = rerank(item["question"], hits)
            rerank_seconds += perf_counter() - started
            raw.append([hit.source_id for hit in hits[:5]])
            reranked.append([hit.source_id for hit in refined])
            cases.append(
                {
                    "id": item["id"],
                    "rrf": raw[-1],
                    "reranked": reranked[-1],
                    "hits": [hit.model_dump(mode="json") for hit in hits[:5]],
                }
            )
        relevant = [set(item["relevant"]) for item in golden]
        report = {
            "embedding_model": model,
            "reranker": "Xenova/ms-marco-MiniLM-L-6-v2",
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            "golden_sha256": hashlib.sha256(golden_path.read_bytes()).hexdigest(),
            "documents": len(corpus),
            "questions": len(golden),
            "rrf": retrieval_metrics(raw, relevant),
            "reranked": retrieval_metrics(reranked, relevant),
            "seconds": {
                "index": round(indexed_seconds, 3),
                "search_total": round(search_seconds, 3),
                "rerank_total_including_load": round(rerank_seconds, 3),
            },
            "faithfulness": "not_run_requires_live_judge",
            "cases": cases,
        }
        output = ROOT / "test-results/rag-eval.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "cases"}))
        baseline = json.loads((ROOT / "evals/baseline.json").read_text(encoding="utf-8"))
        for mode in ("rrf", "reranked"):
            print(
                json.dumps({"mode": mode, "MRR_delta": report[mode]["MRR"] - baseline[mode]["MRR"]})
            )
            assert report[mode]["hit@5"] >= baseline[mode]["hit@5"], mode
    finally:
        with admin_engine.begin() as connection:
            connection.execute(delete(KnowledgeChunk).where(col(KnowledgeChunk.slug).in_(slugs)))
