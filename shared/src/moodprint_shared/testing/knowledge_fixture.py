"""Offline deterministic retrieval over explicitly synthetic articles."""

import asyncio
import math
import re
import unicodedata
from importlib.resources import files

from pydantic import Field

from moodprint_shared.contracts.base import AgeBand, FrozenDTO
from moodprint_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable
from moodprint_shared.contracts.knowledge import (
    KnowledgeChunk,
    KnowledgeQuery,
    KnowledgeResult,
    RetrievalScope,
    SourceCitation,
)


class FixtureArticle(FrozenDTO):
    chunk_id: str
    text: str
    citation: SourceCitation
    age_bands: list[AgeBand]
    topics: list[str]
    language: str


class FixtureCorpus(FrozenDTO):
    corpus_version: str
    articles: list[FixtureArticle] = Field(default_factory=list[FixtureArticle])


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return set(re.findall(r"\w+", normalized))


class FixtureKnowledgeRetriever:
    def __init__(self) -> None:
        fixture = files("moodprint_shared.testing").joinpath("data/knowledge_fixture.json")
        self._corpus = FixtureCorpus.model_validate_json(fixture.read_text(encoding="utf-8"))

    async def search(
        self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float
    ) -> KnowledgeResult:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise KnowledgeTimeout()
        if scope.corpus_version is not None and scope.corpus_version != self._corpus.corpus_version:
            raise KnowledgeUnavailable()
        try:
            async with asyncio.timeout(timeout_s):
                # Yield so cancellation remains observable even for this in-memory adapter.
                await asyncio.sleep(0)
                tokens = _tokens(query.text)
                filters = query.filters
                chunks: list[KnowledgeChunk] = []
                for article in self._corpus.articles:
                    if filters.age_band is not None and filters.age_band not in article.age_bands:
                        continue
                    if filters.topics and not set(filters.topics).intersection(article.topics):
                        continue
                    if filters.country_scope and not set(filters.country_scope).intersection(
                        article.citation.country_scope
                    ):
                        continue
                    if filters.languages and article.language not in filters.languages:
                        continue
                    overlap = tokens.intersection(
                        _tokens(article.text + " " + article.citation.title)
                    )
                    if not overlap:
                        continue
                    chunks.append(
                        KnowledgeChunk(
                            chunk_id=article.chunk_id,
                            text=article.text,
                            citation=article.citation.model_copy(deep=True),
                            score=len(overlap) / len(tokens),
                            match_kind="fixture",
                        )
                    )
                chunks.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
                selected = chunks[: query.top_k]
                return KnowledgeResult(
                    status="ok" if selected else "no_results",
                    chunks=selected,
                    corpus_version=self._corpus.corpus_version,
                    latency_ms=0,
                )
        except TimeoutError:
            raise KnowledgeTimeout() from None
