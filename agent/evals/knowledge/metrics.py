"""Retrieval metrics. No model judge."""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(relevant: set[str], ranked: Sequence[str], k: int) -> float:
    if not relevant:
        return 1.0
    hit = set(ranked[:k]) & relevant
    return len(hit) / min(len(relevant), k)


def hit_at_k(relevant: set[str], ranked: Sequence[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def mrr_at_k(relevant: set[str], ranked: Sequence[str], k: int) -> float:
    for index, document_id in enumerate(ranked[:k], start=1):
        if document_id in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(grades: dict[str, int], ranked: Sequence[str], k: int) -> float:
    def gain(document_id: str) -> float:
        grade = grades.get(document_id, 0)
        return (2**grade) - 1

    dcg = sum(
        gain(document_id) / math.log2(index + 1)
        for index, document_id in enumerate(ranked[:k], start=1)
    )
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(
        ((2**grade) - 1) / math.log2(index + 1) for index, grade in enumerate(ideal, start=1)
    )
    if idcg == 0:
        return 0.0
    return dcg / idcg


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]
