"""KnowledgeService: validation, error mapping and privacy (I-KB-20..30 at service level)."""

from __future__ import annotations

import logging
import uuid
from datetime import date

import pytest
from app.core.errors import ApiError
from app.modules.knowledge.schemas import ChunkRead
from app.modules.knowledge.service import KnowledgeService, parse_age, parse_topic
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable
from moodprint_shared.contracts.knowledge import (
    KnowledgeChunk,
    KnowledgeQuery,
    KnowledgeResult,
    RetrievalScope,
    SourceCitation,
)


class FakeRetriever:
    def __init__(self, result: KnowledgeResult | Exception) -> None:
        self.result = result
        self.queries: list[KnowledgeQuery] = []

    async def search(
        self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float
    ) -> KnowledgeResult:
        del scope, timeout_s
        self.queries.append(query)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _service(result: KnowledgeResult | Exception) -> tuple[KnowledgeService, FakeRetriever]:
    retriever = FakeRetriever(result)
    return KnowledgeService(None, retriever, AppConfig()), retriever  # type: ignore[arg-type]


def _ok_result() -> KnowledgeResult:
    citation = SourceCitation(
        source_id="mp-authored",
        document_id="kb-def-ba-dau-hieu",
        title="Ba dấu hiệu",
        publisher="MoodPrint",
        url=None,
        section="Cố ý gây hại",
        published_at=None,
        last_reviewed=date(2026, 11, 9),
        applicability="Thẻ biên soạn",
        country_scope=["VN"],
    )
    chunk = KnowledgeChunk(
        chunk_id="kb-def-ba-dau-hieu#000-aaaaaaaa",
        text="Nội dung.",
        citation=citation,
        score=0.8,
        match_kind="vector",
    )
    return KnowledgeResult(
        status="ok", chunks=[chunk], corpus_version="kb-20261109-06", latency_ms=5
    )


async def _search(service: KnowledgeService, **overrides: object):
    values: dict[str, object] = {
        "q": "bị nhắn tin dọa",
        "topic": None,
        "age": None,
        "language": "vi",
        "limit": 5,
        "request_id": "req-1",
    }
    values.update(overrides)
    return await service.search(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("q", ["", "   ", "x" * 301])
async def test_bad_query_text_is_422(q: str) -> None:
    service, retriever = _service(_ok_result())
    with pytest.raises(ApiError) as error:
        await _search(service, q=q)
    assert error.value.status_code == 422
    assert retriever.queries == []  # never reached the retriever


@pytest.mark.parametrize("limit", [0, -1, 21, 500])
async def test_limit_out_of_range_is_422(limit: int) -> None:
    service, _ = _service(_ok_result())
    with pytest.raises(ApiError) as error:
        await _search(service, limit=limit)
    assert error.value.status_code == 422


def test_age_and_topic_validation() -> None:
    assert parse_age("11–13") == "11-13"  # en dash from the UI maps to the API form
    assert parse_age("14-17") == "14-17"
    assert parse_age(None) is None
    for bad in ("9-10", "adult", "11-17"):
        with pytest.raises(ApiError):
            parse_age(bad)
    assert parse_topic("cyber") == "cyber"
    with pytest.raises(ApiError):
        parse_topic("not-a-topic")
    with pytest.raises(ApiError):
        parse_topic("cyber'; drop table knowledge.chunks; --")


async def test_no_results_is_a_normal_empty_response_not_an_error() -> None:
    empty = KnowledgeResult(
        status="no_results", chunks=[], corpus_version="kb-20261109-06", latency_ms=3
    )
    service, _ = _service(empty)
    result = await _search(service)
    assert result.status == "no_results"
    assert result.chunks == []


async def test_unavailable_and_timeout_map_to_502_upstream_error() -> None:
    service, _ = _service(KnowledgeUnavailable("down", details={"reason": "database"}))
    with pytest.raises(ApiError) as error:
        await _search(service)
    assert error.value.status_code == 502
    assert error.value.code == "upstream_error"
    assert error.value.details == {"reason": "database"}
    service, _ = _service(KnowledgeTimeout())
    with pytest.raises(ApiError) as timeout:
        await _search(service)
    assert timeout.value.status_code == 502
    assert timeout.value.details == {"reason": "timeout"}


async def test_filters_reach_the_retriever() -> None:
    service, retriever = _service(_ok_result())
    await _search(service, topic="cyber", age="11-13", limit=7)
    sent = retriever.queries[0]
    assert sent.top_k == 7
    assert sent.filters.topics == ["cyber"]
    assert sent.filters.age_band == "11-13"


async def test_the_query_text_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    canary = f"ZZ-CANARY-{uuid.uuid4()}"
    service, _ = _service(_ok_result())
    with caplog.at_level(logging.DEBUG):
        await _search(service, q=canary)
    assert canary not in caplog.text
    assert "q_len=" in caplog.text


def test_search_response_does_not_expose_internal_fields() -> None:
    fields = set(ChunkRead.model_fields) | set(
        ChunkRead.model_fields["citation"].annotation.model_fields
    )  # type: ignore[union-attr]
    for forbidden in ("licence_note", "licence_quote", "embedding", "fts", "cache_path"):
        assert forbidden not in fields
