"""Validate the document/job again after admission, before any external text send."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests import test_embeddings
from tests.test_embeddings import add_memory, queue_memory
from tests.test_guest_embeddings import PausedProvider, queue, semantic_guest
from tests.test_guest_paid_dispatch import ledger

pytestmark = pytest.mark.postgres
embedding_env = test_embeddings.embedding_env


async def prepared(app):
    from app.infrastructure.database.models import Memory, PrivateItem

    guest, settings, mid = await semantic_guest(app, started_ago=timedelta(minutes=1))
    settings.embedding_job_batch_size = 1
    async with app.state.database.sessions.begin() as db:
        source = PrivateItem(user_id=guest.user_id, text="approved source")
        db.add(source)
        await db.flush()
        memory = await db.get(Memory, mid)
        memory.source_id, memory.source_version = source.id, 1
        sid = source.id
    await queue(app, settings, mid)
    return guest, settings, mid, sid


async def paused_worker(app, settings, monkeypatch):
    from app.ai import embeddings

    reached, resume = asyncio.Event(), asyncio.Event()
    original = embeddings._guest_embedding_call

    async def barrier(*args, **kwargs):
        reached.set()
        await resume.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(embeddings, "_guest_embedding_call", barrier)
    provider = PausedProvider()
    provider.release.set()
    task = asyncio.create_task(embeddings.process_embedding_jobs(app.state.database, settings, provider))
    await asyncio.wait_for(reached.wait(), 5)
    return provider, task, resume


async def no_disclosure(app, provider):
    from app.ai.embedding_models import MemoryEmbedding
    from app.modules.guests.models import GuestOperationLink

    assert provider.calls == [], "stale document text was disclosed"
    days, reservations, _ = await ledger(app)
    assert all(row.dispatched_at is None for row in reservations)
    assert all(row.reserved_nano_usd == row.spent_nano_usd == 0 for row in days)
    async with app.state.database.sessions() as db:
        assert not (await db.scalars(select(MemoryEmbedding))).all()
        assert all(row.state == "completed" for row in (await db.scalars(select(GuestOperationLink))).all())


@pytest.mark.parametrize("mutation", ["edit", "delete", "source"])
async def test_invalidated_document_never_reaches_provider(clients, monkeypatch, mutation):
    from app.infrastructure.database.models import PrivateItem, User

    app, _ = clients
    guest, settings, mid, sid = await prepared(app)
    provider, task, resume = await paused_worker(app, settings, monkeypatch)
    try:
        headers = {"Idempotency-Key": str(uuid4())}
        if mutation == "edit":
            response = await guest.client.patch(f"/api/v1/memories/{mid}",
                json={"text": "new approved text", "expectedVersion": 1}, headers=headers)
            assert response.status_code == 200, response.text
        elif mutation == "delete":
            response = await guest.client.request("DELETE", f"/api/v1/memories/{mid}",
                json={"expectedVersion": 1}, headers=headers)
            assert response.status_code == 200, response.text
        else:
            # The source can become stale without cancelling this document's job.
            async with app.state.database.sessions.begin() as db:
                await db.get(User, guest.user_id, with_for_update=True)
                source = await db.get(PrivateItem, sid)
                source.version += 1
    finally:
        resume.set()
        await asyncio.wait_for(task, 5)
    await no_disclosure(app, provider)


@pytest.mark.parametrize("mutation", ["stolen", "expired"])
async def test_stolen_or_expired_document_lease_blocks_dispatch(clients, monkeypatch, mutation):
    from app.ai.embedding_models import EmbeddingJob
    from app.modules.guests.policy import database_time

    app, _ = clients
    _, settings, _, _ = await prepared(app)
    provider, task, resume = await paused_worker(app, settings, monkeypatch)
    try:
        async with app.state.database.sessions.begin() as db:
            job = await db.scalar(select(EmbeddingJob).with_for_update())
            if mutation == "stolen":
                job.lease_token = uuid4()
            else:
                job.lease_until = await database_time(db) - timedelta(milliseconds=1)
    finally:
        resume.set()
        await asyncio.wait_for(task, 5)
    await no_disclosure(app, provider)


async def test_unrelated_personal_edit_preserves_document_dispatch(clients, monkeypatch):
    from app.infrastructure.database.models import PrivateItem, User

    app, _ = clients
    guest, settings, _, _ = await prepared(app)
    provider, task, resume = await paused_worker(app, settings, monkeypatch)
    try:
        async with app.state.database.sessions.begin() as db:
            user = await db.get(User, guest.user_id, with_for_update=True)
            user.data_version += 1
            db.add(PrivateItem(user_id=user.id, text="unrelated approved personal item"))
    finally:
        resume.set()
        await asyncio.wait_for(task, 5)
    assert provider.calls == [("Tôi thích đọc sách", "document")]


async def test_query_embedding_keeps_separate_funded_scope(clients):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.core.security import Actor
    from app.modules.guests.models import GuestUsage

    app, _ = clients
    guest, settings, _, _ = await prepared(app)
    provider = PausedProvider()
    provider.release.set()
    await process_embedding_jobs(app.state.database, settings, provider)
    actor = Actor(guest.user_id, guest.session_id, 1, "guest")
    await retrieve_memories(app.state.database, settings, actor, "may", "sách", 1, provider=provider,
        operation_key="query-separate-funding")
    assert [kind for _, kind in provider.calls] == ["document", "query"]
    _, reservations, _ = await ledger(app)
    assert len(reservations) == 2 and all(row.state == "settled" for row in reservations)
    async with app.state.database.sessions() as db:
        assert (await db.get(GuestUsage, guest.user_id)).semantic_memories == 1


@pytest.mark.parametrize("mutation", ["none", "delete"])
async def test_registered_document_worker_uses_same_resource_fence(clients, embedding_env, monkeypatch, mutation):
    from app.ai.embedding_models import MemoryEmbedding

    app, actors = clients
    database, settings, actor, _ = embedding_env
    mid = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, mid)
    provider, task, resume = await paused_worker(app, settings, monkeypatch)
    try:
        if mutation == "delete":
            response = await actors[0][0].request("DELETE", f"/api/v1/memories/{mid}",
                json={"expectedVersion": 1}, headers={"Idempotency-Key": str(uuid4())})
            assert response.status_code == 200, response.text
    finally:
        resume.set()
        await asyncio.wait_for(task, 5)
    assert len(provider.calls) == (1 if mutation == "none" else 0)
    days, reservations, _ = await ledger(app)
    assert days == reservations == [], "registered work has no guest budget policy"
    async with database.sessions() as db:
        assert len((await db.scalars(select(MemoryEmbedding))).all()) == (1 if mutation == "none" else 0)
