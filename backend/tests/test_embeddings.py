"""Synthetic embedding boundary and real PostgreSQL privacy/lifecycle regressions."""

import asyncio
import json
import logging
import warnings
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, inspect, select, update

from app.ai import embedding_models  # noqa: F401 -- register before the database fixture


class SyntheticProvider:
    def __init__(self, callback=None, failure=False):
        self.calls = []
        self.callback = callback
        self.failure = failure

    async def embed(self, text, input_type):
        from app.ai.voyage import EmbeddingError

        self.calls.append((text, input_type))
        if self.callback:
            await self.callback()
        if self.failure:
            raise EmbeddingError("embedding_provider_unavailable")
        # Small deterministic topic projection padded to configured 256 dimensions.
        return ([1.0, 0.0] if "sách" in text else [0.0, 1.0]) + [0.0] * 254


@pytest.mark.postgres
async def test_worker_observability_reports_queue_and_retries_without_personal_data(embedding_env, caplog):
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id, 'CONFIDENTIAL_SENTINEL')
    await queue_memory(database, settings, mid)
    with caplog.at_level(logging.INFO, logger='moodprint.embeddings'):
        await process_embedding_jobs(database, settings, provider=SyntheticProvider(failure=True))
    messages = [record.getMessage() for record in caplog.records if record.name == 'moodprint.embeddings']
    assert any('embedding_job_attempt state=retry attempt=1' in message for message in messages)
    assert any('embedding_queue_state' in message and 'retry=1' in message for message in messages)
    assert 'CONFIDENTIAL_SENTINEL' not in '\n'.join(messages)
    assert str(actor.user_id) not in '\n'.join(messages)
    assert str(mid) not in '\n'.join(messages)


@pytest.fixture
async def embedding_env(clients):
    from app.ai.models import AiPreference
    from app.core.config import Settings
    from app.core.security import Actor
    from app.infrastructure.database.models import AuthSession, Consent

    app, actors = clients
    uid = actors[0][1]
    settings = Settings(
        semantic_memory_enabled=True, voyage_api_key="synthetic", voyage_dimensions=256
    )
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(Consent).where(Consent.user_id == uid).values(enabled=True))
        db.add(AiPreference(user_id=uid, semantic_memory_enabled=True, policy_version="ai-data-v1"))
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, 1)
    return app.state.database, settings, actor, actors[1][1]


async def add_memory(database, uid, text="Tôi đọc sách để thư giãn", **kwargs):
    from app.infrastructure.database.models import Memory

    async with database.sessions.begin() as db:
        memory = Memory(
            user_id=uid,
            bot_id=kwargs.pop("bot_id", "may"),
            text=text,
            proposal_id=uuid4(),
            **kwargs,
        )
        db.add(memory)
        await db.flush()
        return memory.id


async def queue_memory(database, settings, mid):
    from app.ai.embeddings import enqueue_memory
    from app.infrastructure.database.models import Memory

    async with database.sessions.begin() as db:
        await enqueue_memory(db, await db.get(Memory, mid), settings)


@pytest.mark.postgres
async def test_jobs_deduplicate_and_publish_only_approved_memory(embedding_env):
    from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    await queue_memory(database, settings, mid)
    provider = SyntheticProvider()
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EmbeddingJob)) == 1
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
        job = await db.scalar(select(EmbeddingJob))
        assert job.status == "succeeded" and job.attempts == 1
    assert provider.calls == [("Tôi đọc sách để thư giãn", "document")]


@pytest.mark.postgres
async def test_changed_memory_during_provider_call_cannot_publish(embedding_env):
    from app.ai.embedding_models import MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs
    from app.infrastructure.database.models import Memory

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)

    async def edit():
        async with database.sessions.begin() as db:
            await db.execute(
                update(Memory).where(Memory.id == mid).values(version=2, text="Tôi thích đi bộ")
            )

    await process_embedding_jobs(database, settings, provider=SyntheticProvider(callback=edit))
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0


@pytest.mark.postgres
async def test_failed_jobs_back_off_without_holding_provider_transaction(embedding_env):
    from app.ai.embedding_models import EmbeddingJob
    from app.ai.embeddings import process_embedding_jobs
    from app.infrastructure.database.models import now

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    provider = SyntheticProvider(failure=True)
    await process_embedding_jobs(database, settings, provider=provider)
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions() as db:
        job = await db.scalar(select(EmbeddingJob))
        assert job.status == "retry" and job.attempts == 1 and job.available_at > now()
        assert job.last_error == "embedding_provider_unavailable"
    assert len(provider.calls) == 1


@pytest.mark.postgres
async def test_retrieval_filters_tenant_and_bot_before_top_k(embedding_env):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.ai.models import AiPreference
    from app.infrastructure.database.models import Consent

    database, settings, actor, other_uid = embedding_env
    async with database.sessions.begin() as db:
        db.add(
            AiPreference(
                user_id=other_uid, semantic_memory_enabled=True, policy_version="ai-data-v1"
            )
        )
        await db.execute(update(Consent).where(Consent.user_id == other_uid).values(enabled=True))
    relevant = await add_memory(database, actor.user_id)
    unrelated = await add_memory(database, actor.user_id, "Tôi thích bơi vào cuối tuần")
    other_bot = await add_memory(database, actor.user_id, "Tôi đọc sách về toán", bot_id="guong")
    foreign = await add_memory(database, other_uid, "Tôi đọc sách của người khác")
    for mid in (relevant, unrelated, other_bot, foreign):
        await queue_memory(database, settings, mid)
    await process_embedding_jobs(database, settings, provider=SyntheticProvider())
    provider = SyntheticProvider()
    result = await retrieve_memories(
        database, settings, actor, "may", "đọc sách", 1, provider=provider
    )
    assert result == ["Tôi đọc sách để thư giãn"]
    assert provider.calls == [("đọc sách", "query")]
@pytest.mark.postgres
async def test_no_indexing_before_semantic_optin_or_after_mem_revocation(embedding_env):
    from app.ai.embedding_models import EmbeddingJob
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.ai.models import AiPreference
    from app.infrastructure.database.models import Consent

    database, settings, actor, _ = embedding_env
    await add_memory(database, actor.user_id)
    async with database.sessions.begin() as db:
        await db.execute(update(AiPreference).values(semantic_memory_enabled=False))
    provider = SyntheticProvider()
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EmbeddingJob)) == 0
    async with database.sessions.begin() as db:
        await db.execute(
            update(Consent)
            .where(Consent.user_id == actor.user_id, Consent.purpose == "MEM")
            .values(enabled=False)
        )
    assert (
        await retrieve_memories(database, settings, actor, "may", "sách", 1, provider=provider)
    ) == ["Tôi đọc sách để thư giãn"]
    assert provider.calls == []


@pytest.mark.postgres
async def test_concurrent_workers_do_not_double_embed_live_leased_job(embedding_env):
    from app.ai.embedding_models import MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    started, release = asyncio.Event(), asyncio.Event()

    async def pause():
        started.set()
        await asyncio.wait_for(release.wait(), timeout=5)

    first = SyntheticProvider(callback=pause)
    worker = asyncio.create_task(process_embedding_jobs(database, settings, provider=first))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        second = SyntheticProvider()
        assert await process_embedding_jobs(database, settings, provider=second) == 0
        assert second.calls == []
    finally:
        release.set()
        await worker
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
    assert len(first.calls) == 1


@pytest.mark.postgres
async def test_job_retry_exhaustion_is_terminal_without_reconciliation_reset(embedding_env):
    from app.ai.embedding_models import EmbeddingJob
    from app.ai.embeddings import process_embedding_jobs
    from app.infrastructure.database.models import now

    database, settings, actor, _ = embedding_env
    settings.embedding_max_attempts = 2
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    provider = SyntheticProvider(failure=True)
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions.begin() as db:
        await db.execute(update(EmbeddingJob).values(available_at=now() - timedelta(seconds=1)))
    await process_embedding_jobs(database, settings, provider=provider)
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions() as db:
        job = await db.scalar(select(EmbeddingJob))
        assert job.status == "failed" and job.attempts == 2
    assert len(provider.calls) == 2


@pytest.mark.postgres
async def test_config_change_never_compares_incompatible_vectors(embedding_env):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories

    database, settings, actor, _ = embedding_env
    await add_memory(database, actor.user_id)
    await process_embedding_jobs(database, settings, provider=SyntheticProvider())
    settings.voyage_dimensions = 512
    provider = SyntheticProvider()
    assert await retrieve_memories(
        database, settings, actor, "may", "sách", 1, provider=provider
    ) == ["Tôi đọc sách để thư giãn"]
    assert provider.calls == []


@pytest.mark.postgres
async def test_cancelled_config_job_can_be_reconciled_when_config_returns(embedding_env):
    from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    async with database.sessions.begin() as db:
        await db.execute(update(EmbeddingJob).values(status="cancelled"))
    await process_embedding_jobs(database, settings, provider=SyntheticProvider())
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1


@pytest.mark.postgres
async def test_vector_schema_reflects_without_unknown_type_drift(database):
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        async with database.connect() as conn:
            await conn.run_sync(
                lambda sync: inspect(sync).get_columns("memory_embeddings", schema="moodprint")
            )
    assert not any("Did not recognize type" in str(w.message) for w in captured)


@pytest.mark.postgres
async def test_vietnamese_retrieval_contract_uses_semantics_and_similarity_threshold(embedding_env):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories

    dataset = json.loads(
        (Path(__file__).parent / "fixtures/memory_retrieval_vi.json").read_text(encoding="utf-8")
    )
    vectors = {
        row["text"]: row["vector"] + [0.0] * 251 for row in dataset["memories"] + dataset["queries"]
    }

    class TopicProvider:
        async def embed(self, text, input_type):
            return vectors[text]

    database, settings, actor, _ = embedding_env
    for row in dataset["memories"]:
        await add_memory(database, actor.user_id, row["text"])
    await process_embedding_jobs(database, settings, provider=TopicProvider())
    for query in dataset["queries"]:
        expected = next(
            row["text"] for row in dataset["memories"] if row["id"] == query["expected"]
        )
        assert await retrieve_memories(
            database, settings, actor, "may", query["text"], 1, provider=TopicProvider()
        ) == [expected]


@pytest.mark.postgres
async def test_unrelated_user_data_revision_does_not_reembed_approved_memories(embedding_env):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.infrastructure.database.models import User

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    provider = SyntheticProvider()
    await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == actor.user_id).values(data_version=2))
    await queue_memory(database, settings, mid)
    await process_embedding_jobs(database, settings, provider=provider)
    assert await retrieve_memories(
        database, settings, actor, "may", "sách", 2, provider=provider
    ) == ["Tôi đọc sách để thư giãn"]
    assert [kind for _, kind in provider.calls] == ["document", "query"]


@pytest.mark.postgres
async def test_reconciliation_indexes_missing_memories_in_bounded_unstarved_batches(embedding_env):
    from app.ai.embedding_models import MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    settings.embedding_job_batch_size = 2
    for text in (
        "Tôi đọc sách A",
        "Tôi đọc sách B",
        "Tôi đọc sách C",
        "Tôi đọc sách D",
        "Tôi đọc sách E",
    ):
        await add_memory(database, actor.user_id, text)
    provider = SyntheticProvider()
    for _ in range(3):
        await process_embedding_jobs(database, settings, provider=provider)
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 5
    assert len(provider.calls) == 5


@pytest.mark.postgres
async def test_no_external_query_without_index_optin_or_caunoi_and_lexical_fallback(embedding_env):
    from app.ai.embeddings import retrieve_memories
    from app.ai.models import AiPreference

    database, settings, actor, _ = embedding_env
    await add_memory(database, actor.user_id, "Tôi thích bơi vào cuối tuần")
    await add_memory(database, actor.user_id)
    provider = SyntheticProvider()
    assert (
        await retrieve_memories(database, settings, actor, "may", "sách", 1, provider=provider)
    )[0] == "Tôi đọc sách để thư giãn"
    assert (
        await retrieve_memories(database, settings, actor, "caunoi", "sách", 1, provider=provider)
        == []
    )
    async with database.sessions.begin() as db:
        await db.execute(
            update(AiPreference)
            .where(AiPreference.user_id == actor.user_id)
            .values(semantic_memory_enabled=False)
        )
    assert (
        await retrieve_memories(database, settings, actor, "may", "sách", 1, provider=provider)
    )[0] == "Tôi đọc sách để thư giãn"
    assert provider.calls == []


@pytest.mark.postgres
async def test_revocation_during_query_prevents_memory_return(embedding_env):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.infrastructure.database.models import Consent, User

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    await process_embedding_jobs(database, settings, provider=SyntheticProvider())

    async def revoke():
        async with database.sessions.begin() as db:
            await db.execute(
                update(Consent)
                .where(Consent.user_id == actor.user_id, Consent.purpose == "MEM")
                .values(enabled=False, version=2)
            )
            await db.execute(update(User).where(User.id == actor.user_id).values(data_version=2))

    assert (
        await retrieve_memories(
            database, settings, actor, "may", "sách", 1, provider=SyntheticProvider(callback=revoke)
        )
        == []
    )


@pytest.mark.postgres
async def test_expired_worker_lease_fence_prevents_old_publication(embedding_env):
    from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
    from app.ai.embeddings import process_embedding_jobs
    from app.infrastructure.database.models import now

    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)

    async def supersede():
        async with database.sessions.begin() as db:
            await db.execute(
                update(EmbeddingJob).values(
                    lease_token=uuid4(), lease_until=now() + timedelta(seconds=60)
                )
            )

    await process_embedding_jobs(database, settings, provider=SyntheticProvider(callback=supersede))
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0


async def test_voyage_sends_document_type_and_returns_validated_vector():
    from app.ai.embedding_config import EmbeddingSettings
    from app.ai.voyage import VoyageProvider

    def handler(request):
        assert request.url == "https://api.voyageai.com/v1/embeddings"
        body = json.loads(request.content)
        assert body["input"] == ["Tôi thích đọc sách"]
        assert body["input_type"] == "document"
        assert body["output_dimension"] == 256
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0] * 256}]})

    settings = EmbeddingSettings(voyage_api_key="synthetic", voyage_dimensions=256)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        vector = await VoyageProvider(settings, client=client).embed(
            "Tôi thích đọc sách", "document"
        )
    assert len(vector) == 256 and vector[0] == 1.0


@pytest.mark.parametrize("vector", [[1.0], [float("nan")] * 256, [0.0] * 256])
async def test_voyage_rejects_malformed_or_zero_vectors(vector):
    from app.ai.embedding_config import EmbeddingSettings
    from app.ai.voyage import EmbeddingError, VoyageProvider

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=json.dumps({"data": [{"index": 0, "embedding": vector}]})
            )
        )
    ) as client:
        with pytest.raises(EmbeddingError):
            await VoyageProvider(
                EmbeddingSettings(voyage_api_key="synthetic", voyage_dimensions=256), client=client
            ).embed("approved", "query")


async def test_voyage_provider_errors_are_content_free():
    from app.ai.embedding_config import EmbeddingSettings
    from app.ai.voyage import EmbeddingError, VoyageProvider

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, text="sensitive echo"))
    ) as client:
        with pytest.raises(EmbeddingError) as caught:
            await VoyageProvider(
                EmbeddingSettings(voyage_api_key="synthetic"), client=client
            ).embed("private memory", "document")
    assert str(caught.value) == "embedding_provider_unavailable"


def test_settings_reject_dimensions_before_any_provider_call():
    from pydantic import ValidationError

    from app.ai.embedding_config import EmbeddingSettings

    with pytest.raises(ValidationError):
        EmbeddingSettings(voyage_dimensions=3)


def test_settings_accept_numeric_dimensions_from_environment(monkeypatch):
    from app.ai.embedding_config import EmbeddingSettings

    monkeypatch.setenv("VOYAGE_DIMENSIONS", "1024")
    assert EmbeddingSettings(_env_file=None).voyage_dimensions == 1024


def test_settings_reject_unsupported_environment_dimensions(monkeypatch):
    from pydantic import ValidationError

    from app.ai.embedding_config import EmbeddingSettings

    monkeypatch.setenv("VOYAGE_DIMENSIONS", "3")
    with pytest.raises(ValidationError):
        EmbeddingSettings(_env_file=None)


def test_lexical_fallback_ranks_vietnamese_relevance_over_newer_unrelated_memories():
    from app.ai.embeddings import lexical_rank

    rows = [
        (uuid4(), "Tôi thích bơi vào cuối tuần"),
        (uuid4(), "Tôi đọc sách để thư giãn"),
        (uuid4(), "Món ăn yêu thích là phở"),
    ]
    assert lexical_rank(rows, "đọc sách", 1) == ["Tôi đọc sách để thư giãn"]

