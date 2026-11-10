"""Relevance gate and ranking. Thresholds stay in KnowledgeConfig."""

from __future__ import annotations

from dataclasses import dataclass

from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.knowledge import SourceCitation


@dataclass(frozen=True, slots=True)
class ScoredHit:
    chunk_id: str
    document_id: str
    text: str
    citation: SourceCitation
    score: float
    match_kind: str
    vector_score: float | None
    lexical_score: float | None


@dataclass(frozen=True, slots=True)
class RawHit:
    chunk_id: str
    document_id: str
    text: str
    citation: SourceCitation
    vector_score: float | None = None
    lexical_score: float | None = None


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _rank(hits: list[RawHit], attr: str) -> dict[str, int]:
    present = [hit for hit in hits if getattr(hit, attr) is not None]
    present.sort(key=lambda hit: (-float(getattr(hit, attr)), hit.chunk_id))
    return {hit.chunk_id: index + 1 for index, hit in enumerate(present)}


def score_hits(
    hits: list[RawHit],
    cfg: KnowledgeConfig,
    *,
    top_k: int,
    lexical_only: bool = False,
) -> list[ScoredHit]:
    if not hits:
        return []
    vector_rank = {} if lexical_only else _rank(hits, "vector_score")
    lexical_rank = _rank(hits, "lexical_score")
    span = cfg.vector_cos_hi - cfg.vector_cos_lo
    fused_max = (1.0 + cfg.lexical_weight) / (cfg.rrf_k + 1)
    relevance: list[tuple[RawHit, float | None, float, float]] = []
    for hit in hits:
        vector_score = None if lexical_only else hit.vector_score
        lexical_score = hit.lexical_score
        if vector_score is None:
            vec_rel = 0.0
        elif span <= 0:
            vec_rel = _clamp(vector_score, 0.0, 1.0)
        else:
            vec_rel = _clamp((vector_score - cfg.vector_cos_lo) / span, 0.0, 1.0)
        lex_rel = 0.0 if lexical_score is None else _clamp(lexical_score, 0.0, 1.0)
        relevance.append((hit, vector_score, vec_rel, lex_rel))
    if cfg.gate_scope == "query":
        # Answerable only if some hit clears the gate; then keep every hit above the lower floors.
        if not any(
            vec >= cfg.min_vector_score or lex >= cfg.min_lexical_score
            for _hit, _score, vec, lex in relevance
        ):
            return []
        floor_vector, floor_lexical = cfg.chunk_floor_vector, cfg.chunk_floor_lexical
    else:
        floor_vector, floor_lexical = cfg.min_vector_score, cfg.min_lexical_score
    ranked: list[ScoredHit] = []
    for hit, vector_score, vec_rel, lex_rel in relevance:
        lexical_score = hit.lexical_score
        if vec_rel < floor_vector and lex_rel < floor_lexical:
            continue
        v_rank = vector_rank.get(hit.chunk_id)
        l_rank = lexical_rank.get(hit.chunk_id)
        if cfg.score_mode == "blend":
            weight = _clamp(cfg.blend_vector_weight, 0.0, 1.0)
            score = weight * vec_rel + (1.0 - weight) * lex_rel
        else:
            fused = (0.0 if v_rank is None else 1.0 / (cfg.rrf_k + v_rank)) + (
                0.0 if l_rank is None else cfg.lexical_weight / (cfg.rrf_k + l_rank)
            )
            score = 0.0 if fused_max <= 0 else min(1.0, fused / fused_max)
        if lexical_only or (v_rank is None and l_rank is not None):
            kind = "lexical"
        elif l_rank is None and v_rank is not None:
            kind = "vector"
        else:
            kind = "hybrid"
        ranked.append(
            ScoredHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                text=hit.text,
                citation=hit.citation,
                score=score,
                match_kind=kind,
                vector_score=vector_score,
                lexical_score=lexical_score,
            )
        )
    ranked.sort(key=lambda hit: (-hit.score, hit.chunk_id))
    kept: list[ScoredHit] = []
    per_doc: dict[str, int] = {}
    for hit in ranked:
        count = per_doc.get(hit.document_id, 0)
        if count >= cfg.max_chunks_per_document:
            continue
        per_doc[hit.document_id] = count + 1
        kept.append(hit)
        if len(kept) == top_k:
            break
    return kept
