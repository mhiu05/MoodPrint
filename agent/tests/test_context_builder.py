from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from safevoice_agent.memory.context_builder import MemoryContextBuilder
from safevoice_agent.memory.retrieval import lexical_score
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextRequest
from safevoice_shared.contracts.memory import Memory, MemoryHit

NOW = datetime(2026, 11, 7, tzinfo=UTC)
USER = UUID("10000000-0000-0000-0000-000000000001")


def hit(text="Mình thích trả lời ngắn.", *, score=0.9, age=0, content_hash=None, **changes):
    memory = Memory(
        id=uuid4(),
        owner_id=USER,
        category="preference",
        content=text,
        content_hash=content_hash or text,
        created_at=NOW - timedelta(days=age),
        updated_at=NOW - timedelta(days=age),
        **changes,
    )
    return MemoryHit(memory=memory, score=score)


def request(**changes):
    return ContextRequest(
        auth=AuthContext(USER, None, None, '{"email":"private@example.test"}'),
        conversation_id=uuid4(),
        user_input="Bạn thân",
        linked_case_id=None,
        token_budget=changes.pop("token_budget", 1000),
        nickname="An",
        **changes,
    )


class Search:
    def __init__(self, hits=(), error=None):
        self.hits, self.error = list(hits), error
        self.query = None

    async def search(self, auth, query):
        self.query = query
        if self.error:
            raise self.error
        return self.hits


async def test_memory_included_when_relevant_and_not_every_memory() -> None:
    service = Search([hit(), hit("Không khớp", score=0), hit("Hết hạn", expires_at=NOW)])
    bundle = await MemoryContextBuilder(service, AppConfig(), clock=lambda: NOW).build(request())
    assert [s.kind for s in bundle.sections] == ["identity", "memory"]
    assert bundle.sections[1].text == "Mình thích trả lời ngắn."
    assert service.query.text == "Bạn thân"
    assert service.query.limit == 5


async def test_budget_drops_lowest_priority_and_records_it() -> None:
    service = Search([hit("a" * 90, score=0.9), hit("b" * 90, score=0.5)])
    bundle = await MemoryContextBuilder(service, AppConfig(), clock=lambda: NOW).build(
        request(token_budget=45)
    )
    assert bundle.total_tokens <= 45
    assert not any(s.text == "b" * 90 for s in bundle.sections)
    assert any(d.reason == "token_budget" for d in bundle.dropped)


async def test_dedupes_by_hash_and_has_provenance_on_every_item() -> None:
    service = Search([hit(content_hash="same"), hit(content_hash="same")])
    bundle = await MemoryContextBuilder(service, AppConfig(), clock=lambda: NOW).build(request())
    assert len([s for s in bundle.sections if s.kind == "memory"]) == 1
    assert all(s.provenance and s.provenance[0].retrieved_at == NOW for s in bundle.sections)


async def test_stale_memory_labeled_and_identity_has_no_email() -> None:
    bundle = await MemoryContextBuilder(
        Search([hit(age=91)]), AppConfig(), clock=lambda: NOW
    ).build(request())
    assert bundle.sections[1].provenance[0].stale is True
    assert "private@example.test" not in bundle.model_dump_json()


async def test_memory_service_failure_degrades_with_dropped_reason() -> None:
    bundle = await MemoryContextBuilder(Search(error=RuntimeError("private")), AppConfig()).build(
        request()
    )
    assert bundle.dropped[0].reason == "service_unavailable"
    assert "private" not in bundle.model_dump_json()


async def test_stable_order() -> None:
    a = hit("a", content_hash="a")
    b = hit("b", content_hash="b")
    builder = MemoryContextBuilder(Search([a, b]), AppConfig(), clock=lambda: NOW)
    first = await builder.build(request())
    builder2 = MemoryContextBuilder(Search([b, a]), AppConfig(), clock=lambda: NOW)
    assert first.sections == (await builder2.build(request())).sections


async def test_cancellation_propagates() -> None:
    import asyncio

    with pytest.raises(asyncio.CancelledError):
        await MemoryContextBuilder(Search(error=asyncio.CancelledError()), AppConfig()).build(
            request()
        )


def test_lexical_score_uses_configured_weights() -> None:
    assert lexical_score(
        ts_rank=1, similarity=0.5, recency_decay=0, cfg=AppConfig().memory
    ) == pytest.approx(0.75)
