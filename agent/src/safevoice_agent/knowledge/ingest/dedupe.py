"""Exact and near-duplicate removal. Lower authority_tier wins."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from safevoice_agent.knowledge.textnorm import fold_vietnamese


@dataclass(frozen=True, slots=True)
class DedupeItem:
    document_id: str
    text: str
    authority_tier: int


@dataclass(frozen=True, slots=True)
class DedupeDecision:
    kept: list[str]
    duplicate_of: dict[str, str]


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = fold_vietnamese(text).split()
    if len(words) < 5:
        return {tuple(words)} if words else set()
    return {tuple(words[index : index + 5]) for index in range(len(words) - 4)}


def _jaccard(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union)


def dedupe(items: list[DedupeItem], *, threshold: float = 0.90) -> DedupeDecision:
    ranked = sorted(items, key=lambda item: (item.authority_tier, item.document_id))
    kept: list[DedupeItem] = []
    fingerprints: list[tuple[str, set[tuple[str, ...]]]] = []
    duplicate_of: dict[str, str] = {}
    for item in ranked:
        digest = hashlib.sha256(fold_vietnamese(item.text).encode()).hexdigest()
        shingles = _shingles(item.text)
        match = next(
            (
                kept_id
                for kept_id, kept_shingles, kept_digest in (
                    (
                        existing.document_id,
                        _shingles(existing.text),
                        hashlib.sha256(fold_vietnamese(existing.text).encode()).hexdigest(),
                    )
                    for existing in kept
                )
                if kept_digest == digest or _jaccard(shingles, kept_shingles) >= threshold
            ),
            None,
        )
        if match is None:
            kept.append(item)
            fingerprints.append((digest, shingles))
        else:
            duplicate_of[item.document_id] = match
    return DedupeDecision(kept=[item.document_id for item in kept], duplicate_of=duplicate_of)
