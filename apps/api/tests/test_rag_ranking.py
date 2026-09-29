import pytest

from app.rag.ranking import reciprocal_rank_fusion, retrieval_metrics


def test_rrf_combines_ranks_without_duplicate_votes():
    result = reciprocal_rank_fusion([["a", "a", "b"], ["b", "c"]])
    assert [key for key, _ in result] == ["b", "a", "c"]
    assert dict(result)["a"] == 1 / 61
    assert dict(result)["b"] == 1 / 62 + 1 / 61


def test_metrics_include_misses_and_first_relevant_position():
    result = retrieval_metrics([["wrong", "right"], []], [{"right"}, {"missing"}], k=1)
    assert result == {"hit@1": 0, "MRR": 0.25}
    with pytest.raises(ValueError):
        retrieval_metrics([], [])
