"""Hybrid pgvector retriever. Search SQL lives here because function bodies are scope-limited."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable
from moodprint_shared.contracts.knowledge import (
    KnowledgeChunk,
    KnowledgeQuery,
    KnowledgeResult,
    RetrievalScope,
    SourceCitation,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from moodprint_agent.knowledge.query import prepare_query
from moodprint_agent.knowledge.scoring import RawHit, score_hits

log = logging.getLogger("moodprint.knowledge.retriever")

_VECTOR_SQL = """
select c.chunk_id, c.document_id, c.text, c.heading,
       d.title, d.primary_url, d.published_at, d.last_reviewed, d.applicability,
       d.country_scope, d.licence_class, d.source_id, s.publisher, s.url as source_url,
       1 - (c.embedding <=> cast(:embedding as vector)) as vector_score
from knowledge.chunks c
join knowledge.documents d
  on d.corpus_version = c.corpus_version and d.document_id = c.document_id
join knowledge.sources s on s.source_id = d.source_id
where c.corpus_version = :version
  and d.language = any(cast(:languages as text[]))
  and (cardinality(cast(:countries as text[])) = 0 or d.country_scope && cast(:countries as text[]))
  and (cast(:age as text) is null or cardinality(d.age_bands) = 0 or cast(:age as text) = any(d.age_bands))
  and (cardinality(cast(:topics as text[])) = 0 or d.topics && cast(:topics as text[]))
order by c.embedding <=> cast(:embedding as vector)
limit :limit
"""

_LEXICAL_SQL = """
select c.chunk_id, c.document_id, c.text, c.heading,
       d.title, d.primary_url, d.published_at, d.last_reviewed, d.applicability,
       d.country_scope, d.licence_class, d.source_id, s.publisher, s.url as source_url,
       ts_rank_cd(c.fts, to_tsquery('simple', :tsquery), 32) as lexical_score
from knowledge.chunks c
join knowledge.documents d
  on d.corpus_version = c.corpus_version and d.document_id = c.document_id
join knowledge.sources s on s.source_id = d.source_id
where c.corpus_version = :version
  and d.language = any(cast(:languages as text[]))
  and (cardinality(cast(:countries as text[])) = 0 or d.country_scope && cast(:countries as text[]))
  and (cast(:age as text) is null or cardinality(d.age_bands) = 0 or cast(:age as text) = any(d.age_bands))
  and (cardinality(cast(:topics as text[])) = 0 or d.topics && cast(:topics as text[]))
  and c.fts @@ to_tsquery('simple', :tsquery)
order by lexical_score desc, c.chunk_id
limit :limit
"""


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class RetrievalObservation:
    degraded: bool
    mode: str
    corpus_version: str


def _number(row: dict[str, object], key: str) -> float:
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    raise KnowledgeUnavailable(
        "Search score was not numeric.",
        details={"reason": "database"},
    )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _citation(row: dict[str, object]) -> SourceCitation:
    publisher = str(row["publisher"])
    if row["licence_class"] == "authored":
        publisher = f"MoodPrint biên soạn — dựa trên {publisher}"
    raw_url = row["primary_url"] or row["source_url"]
    url = str(raw_url) if raw_url else None
    heading = str(row["heading"] or "")
    published = row["published_at"]
    reviewed = row["last_reviewed"]
    return SourceCitation(
        source_id=str(row["source_id"]),
        document_id=str(row["document_id"]),
        title=str(row["title"]),
        publisher=publisher,
        url=url,  # type: ignore[arg-type]
        section=heading or None,
        published_at=published if isinstance(published, date) else None,
        last_reviewed=reviewed if isinstance(reviewed, date) else None,
        applicability=str(row["applicability"]),
        country_scope=[str(item) for item in row["country_scope"]],  # type: ignore[union-attr]
    )


class PgVectorKnowledgeRetriever:
    def __init__(
        self,
        engine: AsyncEngine,
        embedder: QueryEmbedder,
        cfg: KnowledgeConfig,
        *,
        clock: Callable[[], float] = time.perf_counter,
        read_role: str | None = "authenticated",
        use_vector: bool = True,
        use_lexical: bool = True,
    ) -> None:
        self.engine = engine
        self.embedder = embedder
        self.cfg = cfg
        self._clock = clock
        self.read_role = read_role
        self.use_vector = use_vector
        self.use_lexical = use_lexical

    async def search(
        self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float
    ) -> KnowledgeResult:
        result, _observation = await self.search_observed(query, scope=scope, timeout_s=timeout_s)
        return result

    async def search_observed(
        self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float
    ) -> tuple[KnowledgeResult, RetrievalObservation]:
        if timeout_s <= 0:
            raise KnowledgeTimeout()
        started = self._clock()
        try:
            async with asyncio.timeout(timeout_s):
                await asyncio.sleep(0)
                return await self._search(query, scope, started)
        except TimeoutError:
            raise KnowledgeTimeout() from None

    async def _search(
        self, query: KnowledgeQuery, scope: RetrievalScope, started: float
    ) -> tuple[KnowledgeResult, RetrievalObservation]:
        prepared = prepare_query(query.text, max_chars=self.cfg.query_max_chars)
        if prepared.empty:
            return self._result([], started, "unpublished"), RetrievalObservation(
                False, "hybrid", ""
            )
        degraded = False
        vector: list[float] | None = None
        embed_budget = max(0.05, self.cfg.embed_timeout_fraction * self.cfg.timeout_s)
        if self.use_vector:
            try:
                async with asyncio.timeout(embed_budget):
                    vector = await self.embedder.embed_query(prepared.embed_text)
            except TimeoutError:
                degraded = True
                log.warning("embed_unavailable")
            except KnowledgeTimeout:
                degraded = True
                log.warning("embed_unavailable")
            except KnowledgeUnavailable as exc:
                if exc.details.get("reason") == "embed_config":
                    raise
                degraded = True
                log.warning("embed_unavailable")
        if vector is not None and len(vector) != self.cfg.embedding_dims:
            raise KnowledgeUnavailable(
                "Query embedding had the wrong size.",
                details={"reason": "embed_config"},
            )
        try:
            version, rows = await self._query(
                query, scope, prepared.tsquery, vector if not degraded else None
            )
        except KnowledgeUnavailable:
            raise
        except Exception as exc:
            raise KnowledgeUnavailable(
                "Knowledge search could not read the corpus.",
                details={"reason": "database"},
            ) from exc
        merged: dict[str, RawHit] = {}
        for row, kind in rows:
            chunk_id = str(row["chunk_id"])
            current = merged.get(chunk_id)
            citation = _citation(row)
            vector_score = _number(row, "vector_score") if kind == "vector" else None
            lexical_score = _number(row, "lexical_score") if kind == "lexical" else None
            if current is None:
                merged[chunk_id] = RawHit(
                    chunk_id=chunk_id,
                    document_id=str(row["document_id"]),
                    text=str(row["text"]),
                    citation=citation,
                    vector_score=vector_score,
                    lexical_score=lexical_score,
                )
            else:
                merged[chunk_id] = RawHit(
                    chunk_id=current.chunk_id,
                    document_id=current.document_id,
                    text=current.text,
                    citation=current.citation,
                    vector_score=current.vector_score if vector_score is None else vector_score,
                    lexical_score=current.lexical_score if lexical_score is None else lexical_score,
                )
        scored = score_hits(
            list(merged.values()),
            self.cfg,
            top_k=query.top_k,
            lexical_only=degraded or vector is None,
        )
        chunks = [
            KnowledgeChunk(
                chunk_id=hit.chunk_id,
                text=hit.text,
                citation=hit.citation,
                score=hit.score,
                match_kind="lexical" if degraded else hit.match_kind,  # type: ignore[arg-type]
            )
            for hit in scored
        ]
        mode = "lexical" if degraded else "hybrid"
        observation = RetrievalObservation(degraded, mode, version)
        return self._result(chunks, started, version), observation

    async def _query(
        self,
        query: KnowledgeQuery,
        scope: RetrievalScope,
        tsquery: str | None,
        vector: list[float] | None,
    ) -> tuple[str, list[tuple[dict[str, object], str]]]:
        filters = {
            "languages": query.filters.languages or ["vi"],
            "countries": query.filters.country_scope,
            "topics": query.filters.topics,
            "age": query.filters.age_band,
        }
        async with self.engine.connect() as conn:
            async with conn.begin():
                if self.read_role:
                    await conn.execute(text("set local role authenticated"))
                await conn.execute(text("set local search_path = public, extensions"))
                await conn.execute(text("set local statement_timeout = '4000ms'"))
                published = (
                    await conn.execute(
                        text(
                            "select version from knowledge.corpus_versions "
                            "where status = 'published'"
                        )
                    )
                ).scalar_one_or_none()
                version = scope.corpus_version or published
                if published is None and scope.corpus_version is None:
                    raise KnowledgeUnavailable(
                        "No published corpus is available.",
                        details={"reason": "no_published_corpus"},
                    )
                if scope.corpus_version and self.read_role and scope.corpus_version != published:
                    raise KnowledgeUnavailable(
                        "That corpus version is not readable.",
                        details={"reason": "corpus_version_not_available"},
                    )
                if version is None:
                    raise KnowledgeUnavailable(
                        "That corpus version is not readable.",
                        details={"reason": "corpus_version_not_available"},
                    )
                if scope.corpus_version and not self.read_role:
                    exists = (
                        await conn.execute(
                            text(
                                "select 1 from knowledge.corpus_versions where version = :version"
                            ),
                            {"version": scope.corpus_version},
                        )
                    ).scalar_one_or_none()
                    if exists is None:
                        raise KnowledgeUnavailable(
                            "That corpus version is not readable.",
                            details={"reason": "corpus_version_not_available"},
                        )
                rows: list[tuple[dict[str, object], str]] = []
                params = {"version": version, **filters}
                if vector is not None and self.use_vector:
                    result = await conn.execute(
                        text(_VECTOR_SQL),
                        {
                            **params,
                            "embedding": _vector_literal(vector),
                            "limit": self.cfg.vector_candidates,
                        },
                    )
                    rows.extend((dict(row), "vector") for row in result.mappings())
                if tsquery and self.use_lexical:
                    result = await conn.execute(
                        text(_LEXICAL_SQL),
                        {**params, "tsquery": tsquery, "limit": self.cfg.lexical_candidates},
                    )
                    rows.extend((dict(row), "lexical") for row in result.mappings())
                return str(version), rows

    def _result(
        self, chunks: list[KnowledgeChunk], started: float, version: str
    ) -> KnowledgeResult:
        elapsed = max(0, int((self._clock() - started) * 1000))
        if not version:
            version = "kb-00000000-00"
        return KnowledgeResult(
            status="ok" if chunks else "no_results",
            chunks=chunks,
            corpus_version=version,
            latency_ms=elapsed,
        )
