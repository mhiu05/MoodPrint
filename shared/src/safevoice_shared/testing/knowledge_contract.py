"""Reusable pytest mixin: supply a ``retriever`` fixture with a synthetic corpus.

The corpus must contain Vietnamese support content for VN, age 11-13 and
topic ``support``, and no content in the synthetic ``zz`` language.
"""

import asyncio

import pytest

from safevoice_shared.contracts.errors import KnowledgeTimeout
from safevoice_shared.contracts.knowledge import (
    KnowledgeFilters,
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeRetriever,
    RetrievalScope,
)


class KnowledgeRetrieverContract:
    async def search(self, retriever: KnowledgeRetriever, **kwargs: object) -> KnowledgeResult:
        return await retriever.search(
            KnowledgeQuery.model_validate({"text": "hỗ trợ", **kwargs}),
            scope=RetrievalScope(request_id="synthetic-contract"),
            timeout_s=1,
        )

    async def test_ok_shape(self, retriever: KnowledgeRetriever) -> None:
        result = await self.search(retriever)
        assert result.status == "ok"
        assert result.chunks
        for chunk in result.chunks:
            assert chunk.citation.source_id
            assert chunk.citation.document_id
            assert 0 <= chunk.score <= 1
        assert result.corpus_version

    async def test_no_results_is_not_error(self, retriever: KnowledgeRetriever) -> None:
        result = await self.search(retriever, text="zzzznomatchsynthetic")
        assert result.status == "no_results"
        assert result.chunks == []

    async def test_top_k_respected(self, retriever: KnowledgeRetriever) -> None:
        result = await self.search(retriever, top_k=1)
        assert len(result.chunks) == 1

    async def test_sorted_by_score(self, retriever: KnowledgeRetriever) -> None:
        result = await self.search(retriever)
        keys = [(-chunk.score, chunk.chunk_id) for chunk in result.chunks]
        assert keys == sorted(keys)

    async def test_filters_apply(self, retriever: KnowledgeRetriever) -> None:
        result = await self.search(retriever, filters=KnowledgeFilters(languages=["zz"]))
        assert result.status == "no_results"
        result = await self.search(
            retriever,
            filters=KnowledgeFilters(age_band="11-13", topics=["support"], country_scope=["VN"]),
        )
        assert result.chunks
        assert all("VN" in chunk.citation.country_scope for chunk in result.chunks)

    async def test_timeout_raises(self, retriever: KnowledgeRetriever) -> None:
        with pytest.raises(KnowledgeTimeout):
            await retriever.search(
                KnowledgeQuery(text="hỗ trợ"),
                scope=RetrievalScope(request_id="timeout"),
                timeout_s=0,
            )

    async def test_cancellation_propagates(self, retriever: KnowledgeRetriever) -> None:
        task = asyncio.create_task(self.search(retriever))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_deterministic(self, retriever: KnowledgeRetriever) -> None:
        first = await self.search(retriever)
        second = await self.search(retriever)
        assert first.chunks == second.chunks
        assert first.corpus_version == second.corpus_version
