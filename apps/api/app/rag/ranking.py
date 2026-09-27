from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], limit: int = 20
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, identifier in enumerate(dict.fromkeys(ranking), start=1):
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + position)
    return sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:limit]


def retrieval_metrics(
    rankings: list[list[str]], relevant: list[set[str]], k: int = 5
) -> dict[str, float]:
    if not rankings or len(rankings) != len(relevant) or k < 1 or any(not row for row in relevant):
        raise ValueError("Avaliação exige perguntas e referências não vazias alinhadas.")
    hits = reciprocal = 0.0
    for ranking, expected in zip(rankings, relevant, strict=True):
        unique = list(dict.fromkeys(ranking))
        hits += float(bool(set(unique[:k]) & expected))
        reciprocal += next((1 / i for i, key in enumerate(unique, 1) if key in expected), 0)
    return {f"hit@{k}": hits / len(rankings), "MRR": reciprocal / len(rankings)}
