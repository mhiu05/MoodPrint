from datetime import date
from typing import Literal, Protocol

from pydantic import Field, HttpUrl, model_validator

from .base import AgeBand, FrozenDTO


class KnowledgeFilters(FrozenDTO):
    age_band: AgeBand | None = None
    topics: list[str] = Field(default_factory=list[str])
    country_scope: list[str] = Field(default_factory=list[str])
    languages: list[str] = Field(default_factory=lambda: ["vi"])


class KnowledgeQuery(FrozenDTO):
    text: str = Field(min_length=1, max_length=1000)
    filters: KnowledgeFilters = Field(default_factory=KnowledgeFilters)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalScope(FrozenDTO):
    request_id: str
    corpus_version: str | None = None


class SourceCitation(FrozenDTO):
    source_id: str
    document_id: str
    title: str
    publisher: str
    url: HttpUrl | None
    section: str | None
    published_at: date | None
    last_reviewed: date | None
    applicability: str
    country_scope: list[str]


class KnowledgeChunk(FrozenDTO):
    chunk_id: str
    text: str
    citation: SourceCitation
    score: float = Field(ge=0, le=1)
    match_kind: Literal["vector", "lexical", "hybrid", "fixture"]


class KnowledgeResult(FrozenDTO):
    status: Literal["ok", "no_results"]
    chunks: list[KnowledgeChunk]
    corpus_version: str
    latency_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def check_status(self) -> "KnowledgeResult":
        if (self.status == "ok") != bool(self.chunks):
            raise ValueError("status must agree with presence of chunks")
        return self


class KnowledgeRetriever(Protocol):
    async def search(
        self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float
    ) -> KnowledgeResult: ...

