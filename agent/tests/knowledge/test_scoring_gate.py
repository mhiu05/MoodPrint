"""Query-level answerability gate versus the first-pass per-chunk gate."""

from __future__ import annotations

from dataclasses import replace

from moodprint_agent.knowledge.scoring import RawHit, score_hits
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.knowledge import SourceCitation


def _citation(document: str) -> SourceCitation:
    return SourceCitation(
        source_id="mp-authored",
        document_id=document,
        title=document,
        publisher="MoodPrint",
        url=None,
        section=None,
        published_at=None,
        last_reviewed=None,
        applicability="test",
        country_scope=["VN"],
    )


def _hit(chunk: str, document: str, *, vector: float | None, lexical: float | None) -> RawHit:
    return RawHit(chunk, document, "text", _citation(document), vector, lexical)


# vec_rel = (cos - 0.20) / 0.60 with the default lo/hi, so cos 0.65 -> 0.75 and cos 0.32 -> 0.2
CFG = replace(
    KnowledgeConfig(),
    min_vector_score=0.5,
    min_lexical_score=0.6,
    chunk_floor_vector=0.1,
    chunk_floor_lexical=0.2,
    lexical_weight=0.0,
)


def test_query_scope_returns_nothing_when_the_best_hit_is_weak() -> None:
    hits = [
        _hit(
            "a#1", "a", vector=0.40, lexical=0.30
        ),  # vec_rel 0.33: above the floor, below the gate
        _hit("b#1", "b", vector=0.35, lexical=0.25),
    ]
    assert score_hits(hits, replace(CFG, gate_scope="query"), top_k=5) == []


def test_query_scope_keeps_weaker_chunks_once_the_query_is_answerable() -> None:
    hits = [
        _hit("a#1", "a", vector=0.65, lexical=0.7),  # strong: opens the gate
        _hit("b#1", "b", vector=0.42, lexical=0.3),  # weak but above the floors
        _hit("c#1", "c", vector=0.18, lexical=0.05),  # below both floors: dropped
    ]
    kept = {hit.document_id for hit in score_hits(hits, replace(CFG, gate_scope="query"), top_k=5)}
    assert kept == {"a", "b"}


def test_chunk_scope_matches_the_first_pass_behaviour() -> None:
    hits = [
        _hit("a#1", "a", vector=0.65, lexical=0.7),
        _hit("b#1", "b", vector=0.42, lexical=0.3),  # below both gates, so dropped per chunk
    ]
    kept = {hit.document_id for hit in score_hits(hits, replace(CFG, gate_scope="chunk"), top_k=5)}
    assert kept == {"a"}


def test_a_strong_lexical_match_alone_opens_the_query_gate() -> None:
    hits = [_hit("a#1", "a", vector=None, lexical=0.9)]
    assert [h.document_id for h in score_hits(hits, replace(CFG, gate_scope="query"), top_k=5)] == [
        "a"
    ]
