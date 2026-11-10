import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals" / "knowledge"))
from metrics import hit_at_k, mrr_at_k, ndcg_at_k, percentile, recall_at_k  # noqa: E402


def test_recall_and_ranking_examples() -> None:
    relevant = {"a", "b"}
    ranked = ["c", "a", "b"]
    assert recall_at_k(relevant, ranked, 5) == 1
    assert hit_at_k(relevant, ranked, 1) == 0
    assert mrr_at_k(relevant, ranked, 10) == 0.5
    score = ndcg_at_k({"a": 2, "b": 1}, ["a", "b"], 10)
    assert score == 1
    assert percentile([1, 2, 3, 4], 0.5) == 2
