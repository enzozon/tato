import math
from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.rag.retrieval import Hit


@lru_cache(maxsize=1)
def cross_encoder() -> TextCrossEncoder:
    return TextCrossEncoder(
        "Xenova/ms-marco-MiniLM-L-6-v2", threads=2, providers=["CPUExecutionProvider"]
    )


def rerank(query: str, hits: list[Hit]) -> list[Hit]:
    if not hits:
        return []
    candidates = hits[:20]
    scores = list(cross_encoder().rerank(query, [hit.content for hit in candidates], batch_size=8))
    if len(scores) != len(candidates) or not all(math.isfinite(score) for score in scores):
        raise ValueError("Scores de reranking inválidos.")
    ordered = sorted(
        zip(candidates, scores, strict=True), key=lambda pair: (-pair[1], str(pair[0].chunk_id))
    )
    return [hit.model_copy(update={"score": score}) for hit, score in ordered[:5]]
