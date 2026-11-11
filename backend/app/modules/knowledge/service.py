"""Read the published corpus and map retriever results onto the Hub envelope."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from safevoice_agent.knowledge.ingest.topics import PRODUCTION_TOPICS
from safevoice_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable, NotFound
from safevoice_shared.contracts.knowledge import (
    KnowledgeFilters,
    KnowledgeQuery,
    KnowledgeRetriever,
    RetrievalScope,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import ApiError
from app.modules.knowledge.schemas import (
    ChunkRead,
    CitationRead,
    CorpusRead,
    DocumentRead,
    SearchRead,
    SectionRead,
    SourceRead,
)

log = logging.getLogger("safevoice.knowledge.api")


def parse_age(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    normalized = value.replace("–", "-").replace("—", "-").replace(" ", "")
    if normalized not in {"11-13", "14-17"}:
        raise ApiError("validation_failed", "Độ tuổi chưa đúng.", 422)
    return normalized


def parse_topic(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value not in PRODUCTION_TOPICS:
        raise ApiError("validation_failed", "Chủ đề chưa đúng.", 422)
    return value


class KnowledgeService:
    def __init__(self, engine: AsyncEngine, retriever: KnowledgeRetriever, cfg: AppConfig) -> None:
        self.engine = engine
        self.retriever = retriever
        self.cfg = cfg

    async def search(
        self,
        *,
        q: str,
        topic: str | None,
        age: str | None,
        language: str,
        limit: int,
        request_id: str,
    ) -> SearchRead:
        if not q.strip() or len(q) > self.cfg.knowledge.query_max_chars:
            raise ApiError("validation_failed", "Câu tìm kiếm chưa đúng.", 422)
        if limit < 1 or limit > 20:
            raise ApiError("validation_failed", "Số kết quả chưa đúng.", 422)
        query = KnowledgeQuery(
            text=q,
            top_k=limit,
            filters=KnowledgeFilters(
                age_band=age,  # type: ignore[arg-type]
                topics=[topic] if topic else [],
                languages=[language] if language else ["vi"],
            ),
        )
        try:
            if isinstance(self.retriever, PgVectorKnowledgeRetriever):
                result, observed = await self.retriever.search_observed(
                    query,
                    scope=RetrievalScope(request_id=request_id),
                    timeout_s=self.cfg.knowledge.timeout_s,
                )
                degraded, mode = observed.degraded, observed.mode
            else:
                result = await self.retriever.search(
                    query,
                    scope=RetrievalScope(request_id=request_id),
                    timeout_s=self.cfg.knowledge.timeout_s,
                )
                degraded, mode = False, "hybrid"
        except KnowledgeTimeout as exc:
            raise ApiError(
                "upstream_error", "Tra cứu chưa kịp trả lời.", 502, details={"reason": "timeout"}
            ) from exc
        except KnowledgeUnavailable as exc:
            raise ApiError(
                "upstream_error",
                "Chưa thể tra cứu tri thức.",
                502,
                details={"reason": str(exc.details.get("reason") or "unavailable")},
            ) from exc
        log.info(
            "knowledge_search request_id=%s q_len=%s status=%s latency_ms=%s corpus_version=%s",
            request_id,
            len(q),
            result.status,
            result.latency_ms,
            result.corpus_version,
        )
        return SearchRead(
            status=result.status,
            corpus_version=result.corpus_version,
            mode=mode,
            degraded=degraded,
            latency_ms=result.latency_ms,
            chunks=[
                ChunkRead(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    score=chunk.score,
                    match_kind=chunk.match_kind,
                    citation=CitationRead(
                        source_id=chunk.citation.source_id,
                        document_id=chunk.citation.document_id,
                        title=chunk.citation.title,
                        publisher=chunk.citation.publisher,
                        url=str(chunk.citation.url) if chunk.citation.url else None,
                        section=chunk.citation.section,
                        published_at=chunk.citation.published_at,
                        last_reviewed=chunk.citation.last_reviewed,
                        applicability=chunk.citation.applicability,
                        country_scope=list(chunk.citation.country_scope),
                    ),
                )
                for chunk in result.chunks
            ],
        )

    async def document(self, document_id: str) -> DocumentRead:
        row = await self._one(
            "select d.document_id, d.title, d.applicability, d.primary_url, d.published_at,"
            " d.last_reviewed, d.country_scope, d.licence_class, d.derived_from, d.source_id,"
            " s.publisher, s.url as source_url"
            " from knowledge.documents d join knowledge.sources s on s.source_id = d.source_id"
            " where d.document_id = :document_id and d.corpus_version = knowledge.published_version()",
            {"document_id": document_id},
        )
        if row is None:
            raise NotFound()
        sections = await self._all(
            "select heading, text from knowledge.chunks"
            " where document_id = :document_id and corpus_version = knowledge.published_version()"
            " order by ordinal",
            {"document_id": document_id},
        )
        publisher = str(row["publisher"])
        if row["licence_class"] == "authored":
            publisher = f"SafeVoice biên soạn — dựa trên {publisher}"
        derived = row["derived_from"] if isinstance(row["derived_from"], list) else []
        return DocumentRead(
            document_id=str(row["document_id"]),
            title=str(row["title"]),
            sections=[
                SectionRead(heading=str(item["heading"]), text=str(item["text"]))
                for item in sections
            ],
            citation=CitationRead(
                source_id=str(row["source_id"]),
                document_id=str(row["document_id"]),
                title=str(row["title"]),
                publisher=publisher,
                url=str(row["primary_url"] or row["source_url"] or "") or None,
                section=None,
                published_at=row["published_at"],
                last_reviewed=row["last_reviewed"],
                applicability=str(row["applicability"]),
                country_scope=list(row["country_scope"]),
            ),
            derived_from=[
                {
                    "sourceId": str(item.get("source_id", "")),
                    "locator": str(item.get("locator", "")),
                }
                for item in derived
                if isinstance(item, dict)
            ],
        )

    async def sources(self) -> list[SourceRead]:
        rows = await self._all(
            "select source_id, publisher, title, url, verified_on, country_scope, licence_class"
            " from knowledge.sources order by source_id",
            {},
        )
        return [
            SourceRead(
                source_id=str(row["source_id"]),
                publisher=str(row["publisher"]),
                title=str(row["title"]),
                url=str(row["url"]) if row["url"] else None,
                verified_on=row["verified_on"],
                country_scope=list(row["country_scope"]),
                licence_class=str(row["licence_class"]),
            )
            for row in rows
        ]

    async def corpus(self) -> CorpusRead:
        row = await self._one(
            "select v.version, v.published_at,"
            " (select count(*) from knowledge.documents d where d.corpus_version = v.version) as documents,"
            " (select count(*) from knowledge.chunks c where c.corpus_version = v.version) as chunks"
            " from knowledge.corpus_versions v where v.status = 'published'",
            {},
        )
        if row is None:
            raise NotFound()
        published = row["published_at"]
        if isinstance(published, datetime):
            published = published.astimezone(UTC).date()
        return CorpusRead(
            version=str(row["version"]),
            documents=int(row["documents"]),
            chunks=int(row["chunks"]),
            published_at=published,
        )

    async def _one(self, sql: str, params: dict[str, object]):
        rows = await self._all(sql, params)
        return rows[0] if rows else None

    async def _all(self, sql: str, params: dict[str, object]):
        async with self.engine.connect() as conn:
            async with conn.begin():
                await conn.execute(text("set local role authenticated"))
                result = await conn.execute(text(sql), params)
                return [dict(row) for row in result.mappings()]
