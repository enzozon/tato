"""Mede inferência CPU local com conteúdo público; não simula carga de produção."""

import ctypes
import json
import platform
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from app.rag.embedding import embed, encoder
from app.rag.reranking import rerank
from app.rag.retrieval import Hit


def peak_mib() -> float:
    if platform.system() == "Windows":

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak",
                    "working",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not query(ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb):
            raise OSError("Não foi possível medir memória do processo.")
        size = counters.peak
    else:
        import resource

        size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() != "Darwin":
            size *= 1024
    return round(size / (1024 * 1024), 2)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    items = list(
        map(json.loads, (root / "knowledge/base.jsonl").read_text(encoding="utf-8").splitlines())
    )[:20]
    hits = [
        Hit(
            chunk_id=uuid5(NAMESPACE_URL, item["slug"]),
            source="public",
            source_id=item["slug"],
            section=item["title"],
            content=item["text"],
        )
        for item in items
    ]
    question = "Dinheiro para imprevistos"
    start = perf_counter()
    embed([question], query=True)
    report = {
        "platform": platform.platform(),
        "encoder_load_seconds": round(perf_counter() - start, 3),
        "encoder_peak_mib": peak_mib(),
        "embedding_model": encoder()[2],
    }
    start = perf_counter()
    rerank(question, hits)
    report.update(
        {
            "reranker_load_and_20_seconds": round(perf_counter() - start, 3),
            "both_models_peak_mib": peak_mib(),
        }
    )
    for name, operation in [
        ("query", lambda: embed([question], query=True)),
        ("rerank_20", lambda: rerank(question, hits)),
    ]:
        start = perf_counter()
        for _ in range(5):
            operation()
        report[f"warm_{name}_mean_seconds"] = round((perf_counter() - start) / 5, 3)
    output = root / "test-results/rag-resources.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
