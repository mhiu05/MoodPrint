"""Revision fences and short owner transactions protect derived journal vectors."""

import asyncio
import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from app.infrastructure.database.models import User, now
from app.modules.journal.ai_models import JournalAiJob, JournalEntryEmbedding
from app.modules.journal.indexing import (
    journal_document,
    process_journal_jobs,
    reconcile_journal_jobs,
)
from app.modules.journal.models import JournalEntry
from tests.fakes import FakeEmbedder
from tests.guest_helpers import add_guest
from tests.social_helpers import key
from tests.test_journal import create, entry, today


@pytest.mark.parametrize("limit", [7000, 7900])
def test_document_metadata_and_text_together_fit_provider_limit(limit):
    from types import SimpleNamespace

    row = SimpleNamespace(local_date=today(), mood=3, text="x"*10000,
                          emotions=["e"*60]*12, factors=["f"*60]*12)
    document = journal_document(row, limit)
    assert len(document) <= 8000
    assert ", ".join(row.emotions) in document and ", ".join(row.factors) in document


async def due(app):
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalAiJob).where(JournalAiJob.status.in_(("pending", "retry"))).values(available_at=now()-timedelta(seconds=1)))


async def tick(app, fake):
    return await process_journal_jobs(app.state.database, app.state.settings, embedder=fake)


async def jobs(app):
    async with app.state.database.sessions() as db:
        return list((await db.scalars(select(JournalAiJob).order_by(JournalAiJob.entry_version))).all())


async def vectors(app):
    async with app.state.database.sessions() as db:
        return list((await db.scalars(select(JournalEntryEmbedding))).all())


async def edit(client, row, **changes):
    response = await client.put(f"/api/v1/journal/entries/{row['id']}", json=entry(expectedVersion=row['version'], **changes), headers=key())
    assert response.status_code == 200, response.text
    return response.json()


async def test_save_enqueues_one_embed_job_after_debounce(journal_configured):
    app, actors = journal_configured
    before = now()
    await create(actors[0][0])
    rows = await jobs(app)
    assert len(rows) == 1 and rows[0].kind == "embed" and rows[0].status == "pending"
    assert rows[0].available_at >= before + timedelta(seconds=19)
    fake = FakeEmbedder(256)
    assert await tick(app, fake) == 0
    assert fake.calls == 0


async def test_draft_is_never_indexed(journal_configured):
    app, actors = journal_configured
    await create(actors[0][0], status="draft")
    assert await jobs(app) == []
    assert await vectors(app) == []


async def test_edit_deletes_stale_vector_in_the_same_transaction(journal_configured):
    app, actors = journal_configured
    row = await create(actors[0][0])
    await due(app)
    await tick(app, FakeEmbedder(256))
    assert len(await vectors(app)) == 1
    await edit(actors[0][0], row, text="Đã đổi nội dung.")
    assert await vectors(app) == []
    assert [(j.entry_version, j.status) for j in await jobs(app)] == [(1, "succeeded"), (2, "pending")]


async def test_rapid_edits_index_only_latest_revision(journal_configured):
    app, actors = journal_configured
    row = await create(actors[0][0])
    for number in range(3):
        row = await edit(actors[0][0], row, text=f"Bản sửa tổng hợp {number}")
    assert [j.entry_version for j in await jobs(app) if j.status != "cancelled"] == [4]
    await due(app)
    fake = FakeEmbedder(256)
    await tick(app, fake)
    assert fake.calls == 1
    assert [v.entry_version for v in await vectors(app)] == [4]


@pytest.mark.parametrize("path", ["route", "retention", "scope_journal", "account", "guest_purge"])
async def test_every_journal_delete_path_removes_derivatives(journal_configured, path):
    from app.jobs.retention import purge_expired
    from app.modules.guests.lifecycle import purge_guest
    from app.modules.users.lifecycle import process_deletions
    from tests.test_journal_intelligence_migration import seed_derivatives

    app, actors = journal_configured
    client, uid = actors[0]
    if path == "guest_purge":
        guest = await add_guest(app)
        client, uid = guest.client, guest.user_id
    row = await create(client)
    identity = UUID(row["id"])
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(JournalAiJob).where(JournalAiJob.entry_id == identity))
        await seed_derivatives(db, uid, identity)
    if path == "route":
        assert (await client.request("DELETE", f"/api/v1/journal/entries/{identity}", json={"expectedVersion": 1}, headers=key())).status_code == 200
    elif path == "retention":
        async with app.state.database.sessions.begin() as db:
            await db.execute(update(JournalEntry).where(JournalEntry.id == identity).values(local_date=today()-timedelta(days=90)))
        await purge_expired(app)
    elif path == "guest_purge":
        from app.modules.guests.models import GuestCleanupJob

        async with app.state.database.sessions.begin() as db:
            (await db.get(User, uid)).status = "deleting"
            job = await db.get(GuestCleanupJob, uid)
            job.lease_token, job.lease_until = uuid4(), now()+timedelta(seconds=30)
            await db.flush()
            assert await purge_guest(db, uid, job.lease_token) == "removed"
    else:
        version = (await client.get("/api/v1/session")).json()["dataVersion"]
        result = await client.post("/api/v1/data-deletions", json={"scope": "journal" if path == "scope_journal" else "account", "expectedVersion": version}, headers=key())
        assert result.status_code == 202, result.text
        await process_deletions(app)
    assert await jobs(app) == []
    assert await vectors(app) == []


async def test_delete_during_lease_never_publishes(journal_configured):
    app, actors = journal_configured
    row = await create(actors[0][0])
    await due(app)
    release = asyncio.Event()
    fake = FakeEmbedder(256, delay=release)
    task = asyncio.create_task(tick(app, fake))
    await asyncio.wait_for(fake.started.wait(), 3)
    try:
        response = await asyncio.wait_for(actors[0][0].request("DELETE", f"/api/v1/journal/entries/{row['id']}", json={"expectedVersion": 1}, headers=key()), 3)
        assert response.status_code == 200
    finally:
        release.set()
        await task
    assert await vectors(app) == [] and await jobs(app) == []


async def test_settings_off_mid_flight_discards_result(journal_configured):
    from tests.test_journal_ai_settings import body

    app, actors = journal_configured
    await create(actors[0][0])
    await due(app)
    release = asyncio.Event()
    fake = FakeEmbedder(256, delay=release)
    task = asyncio.create_task(tick(app, fake))
    await asyncio.wait_for(fake.started.wait(), 3)
    try:
        result = await asyncio.wait_for(actors[0][0].put("/api/v1/journal/ai-settings", json=body(embeddingEnabled=False), headers=key()), 3)
        assert result.status_code == 200
    finally:
        release.set()
        await task
    assert await vectors(app) == []
    assert (await jobs(app))[0].status == "cancelled"


async def test_provider_failure_retries_with_backoff_then_fails(journal_configured):
    app, actors = journal_configured
    await create(actors[0][0])
    fake = FakeEmbedder(256, error=RuntimeError("synthetic private provider detail"))
    for attempt in range(4):
        await due(app)
        before = now()
        await tick(app, fake)
        job = (await jobs(app))[0]
        assert job.status == ("failed" if attempt == 3 else "retry")
        assert job.last_error == "embedding_provider_unavailable"
        if attempt < 3:
            assert job.available_at >= before+timedelta(seconds=5*2**attempt)
    assert fake.calls == 4 and await vectors(app) == []


async def test_daily_cap_defers_to_next_local_day(journal_configured):
    app, actors = journal_configured
    client, uid = actors[0]
    row = await create(client)
    async with app.state.database.sessions.begin() as db:
        for number in range(app.state.settings.journal_embedding_daily_cap_per_user):
            db.add(JournalAiJob(entry_id=UUID(row["id"]), user_id=uid, kind="embed", entry_version=number+10,
                                settings_version=1, model="synthetic", dimensions=256, status="succeeded"))
    await due(app)
    fake = FakeEmbedder(256)
    await tick(app, fake)
    current = next(j for j in await jobs(app) if j.entry_version == 1)
    assert current.status == "retry" and current.available_at > now()+timedelta(minutes=1)
    assert fake.calls == 0


async def test_daily_cap_counts_completion_day_not_enqueue_day(journal_configured):
    app, actors = journal_configured
    app.state.settings.journal_embedding_daily_cap_per_user = 10
    row = await create(actors[0][0])
    async with app.state.database.sessions.begin() as db:
        for number in range(10):
            db.add(JournalAiJob(entry_id=UUID(row["id"]), user_id=actors[0][1], kind="embed", entry_version=number+10,
                                settings_version=1, model="synthetic", dimensions=256, status="succeeded",
                                created_at=now()-timedelta(days=2), available_at=now()))
    await due(app)
    fake = FakeEmbedder(256)
    await tick(app, fake)
    assert fake.calls == 0


async def test_concurrent_workers_reserve_remaining_daily_capacity(journal_configured):
    app, actors = journal_configured
    app.state.settings.journal_embedding_daily_cap_per_user = 10
    app.state.settings.embedding_job_batch_size = 1
    row = await create(actors[0][0])
    await create(actors[0][0], text="Một trang khác")
    async with app.state.database.sessions.begin() as db:
        for number in range(9):
            db.add(JournalAiJob(entry_id=UUID(row["id"]), user_id=actors[0][1], kind="embed", entry_version=number+10,
                                settings_version=1, model="synthetic", dimensions=256, status="succeeded"))
    await due(app)
    release = asyncio.Event()
    first = FakeEmbedder(256, delay=release)
    task = asyncio.create_task(tick(app, first))
    try:
        await asyncio.wait_for(first.started.wait(), 5)
        second = FakeEmbedder(256)
        await tick(app, second)
        assert second.calls == 0
    finally:
        release.set()
        await task


@pytest.mark.parametrize("provider_error", [False, True])
async def test_deleted_running_entry_cannot_reset_successful_daily_usage(journal_configured, provider_error):
    from app.ai.voyage import EmbeddingError

    app, actors = journal_configured
    app.state.settings.journal_embedding_daily_cap_per_user = 10
    app.state.settings.embedding_job_batch_size = 1
    client, uid = actors[0]
    row = await create(client)
    async with app.state.database.sessions.begin() as db:
        for number in range(9):
            db.add(JournalAiJob(entry_id=UUID(row["id"]), user_id=uid, kind="embed", entry_version=number+10,
                                settings_version=1, model="synthetic", dimensions=256, status="succeeded"))
    await due(app)
    gate = asyncio.Event()
    fake = FakeEmbedder(256, delay=gate, error=EmbeddingError("embedding_unconfigured") if provider_error else None)
    task = asyncio.create_task(tick(app, fake))
    try:
        await asyncio.wait_for(fake.started.wait(), 5)
        assert (await client.request("DELETE", f"/api/v1/journal/entries/{row['id']}", json={"expectedVersion": 1}, headers=key())).status_code == 200
    finally:
        gate.set()
        await task
    await create(client, text="Trang mới sau khi xóa")
    await due(app)
    next_provider = FakeEmbedder(256)
    await tick(app, next_provider)
    assert next_provider.calls == int(provider_error)


async def test_ambiguous_provider_failure_keeps_daily_reservation(journal_configured):
    app, actors = journal_configured
    app.state.settings.journal_embedding_daily_cap_per_user = 10
    app.state.settings.embedding_job_batch_size = 1
    row = await create(actors[0][0])
    async with app.state.database.sessions.begin() as db:
        for number in range(9):
            db.add(JournalAiJob(entry_id=UUID(row["id"]), user_id=actors[0][1], kind="embed", entry_version=number+10,
                                settings_version=1, model="synthetic", dimensions=256, status="succeeded"))
    await due(app)
    await tick(app, FakeEmbedder(256, error=RuntimeError("synthetic ambiguous transport loss")))
    await due(app)
    second = FakeEmbedder(256)
    await tick(app, second)
    assert second.calls == 0


async def test_midnight_reservation_guards_both_possible_completion_days(journal_configured, monkeypatch):
    from datetime import UTC, datetime

    from app.infrastructure.database.models import Idempotency
    from app.modules.journal import quota

    app, actors = journal_configured
    app.state.settings.journal_embedding_daily_cap_per_user = 10
    stamp = datetime(2026, 11, 4, 23, 59, 59, tzinfo=UTC)
    monkeypatch.setattr(quota, "now", lambda: stamp)
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, actors[0][1], with_for_update=True)
        user.timezone = "UTC"
        keys = await quota.reserve_daily_capacity(db, user, app.state.settings, stamp+timedelta(seconds=60))
        assert keys == ("2026-11-04", "2026-11-05")
        # A next-day caller sees the pre-midnight in-flight reservation already.
        next_bucket = await db.scalar(select(Idempotency).where(Idempotency.operation == quota.OPERATION, Idempotency.key == keys[1]))
        next_bucket.receipt = {"count": 10}
        monkeypatch.setattr(quota, "now", lambda: stamp+timedelta(seconds=2))
        assert await quota.reserve_daily_capacity(db, user, app.state.settings, stamp+timedelta(seconds=61)) is None
        await quota.settle_daily_capacity(db, user.id, keys, "2026-11-05")
        current_bucket = await db.scalar(select(Idempotency).where(Idempotency.operation == quota.OPERATION, Idempotency.key == keys[0]))
        assert current_bucket.receipt == {"count": 0}
        assert next_bucket.receipt == {"count": 10}


async def test_daily_usage_receipts_outlive_ordinary_idempotency_retention(journal_configured):
    from app.infrastructure.database.models import Idempotency
    from app.jobs.retention import purge_expired
    from app.modules.journal.quota import OPERATION

    app, actors = journal_configured
    async with app.state.database.sessions.begin() as db:
        for operation, key_value, age in ((OPERATION, "retained", 48), (OPERATION, "expired", 80), ("ordinary", "expired", 48)):
            db.add(Idempotency(user_id=actors[0][1], operation=operation, key=key_value, digest="0"*64,
                               receipt={"count": 3}, created_at=now()-timedelta(hours=age)))
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        remaining = (await db.scalars(select(Idempotency))).all()
        assert [(row.operation, row.key) for row in remaining] == [(OPERATION, "retained")]


@pytest.mark.parametrize("scope", ["all_private", "account"])
async def test_usage_receipts_follow_account_lifecycle_without_late_recreation(journal_configured, scope):
    from app.infrastructure.database.models import Idempotency
    from app.modules.journal.quota import OPERATION, settle_daily_capacity
    from app.modules.users.lifecycle import process_deletions

    app, actors = journal_configured
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        for owner in (uid, actors[1][1]):
            db.add(Idempotency(user_id=owner, operation=OPERATION, key="2026-11-04", digest="0"*64, receipt={"count": 1}))
    version = (await client.get("/api/v1/session")).json()["dataVersion"]
    response = await client.post("/api/v1/data-deletions", json={"scope": scope, "expectedVersion": version}, headers=key())
    assert response.status_code == 202, response.text
    await process_deletions(app)
    async with app.state.database.sessions.begin() as db:
        count = len((await db.scalars(select(Idempotency).where(Idempotency.user_id == uid, Idempotency.operation == OPERATION))).all())
        assert count == int(scope == "all_private")
        await settle_daily_capacity(db, uid, ("2026-11-04",), None)
        assert len((await db.scalars(select(Idempotency).where(Idempotency.user_id == uid, Idempotency.operation == OPERATION))).all()) == count
        assert await db.scalar(select(Idempotency).where(Idempotency.user_id == actors[1][1], Idempotency.operation == OPERATION)) is not None


async def test_minor_guest_and_deletion_pending_never_enqueued(journal_configured):
    from tests.conftest import add_actor

    app, actors = journal_configured
    teen, _uid = await add_actor(app, 3, age_band="teen")
    guest = await add_guest(app)
    # Direct worker/backfill input can contain rows which an HTTP age gate refuses.
    async with app.state.database.sessions.begin() as db:
        for uid in (actors[0][1], _uid, guest.user_id):
            db.add(JournalEntry(user_id=uid, local_date=today(), timezone="Asia/Bangkok", mood=3, text="Tổng hợp", status="saved"))
        (await db.get(User, actors[0][1])).deletion_pending = True
    assert await reconcile_journal_jobs(app.state.database, app.state.settings) == 0
    assert await jobs(app) == []
    await teen.aclose()


async def test_reconcile_backfills_existing_entries_in_bounded_batches(journal_configured):
    app, actors = journal_configured
    app.state.settings.embedding_job_batch_size = 10
    async with app.state.database.sessions.begin() as db:
        for number in range(26):
            db.add(JournalEntry(user_id=actors[0][1], local_date=today()-timedelta(days=90 if number == 25 else number),
                                timezone="Asia/Bangkok", mood=3, text="Trang tổng hợp", status="saved"))
    assert await reconcile_journal_jobs(app.state.database, app.state.settings) == 10
    assert len(await jobs(app)) == 10
    await reconcile_journal_jobs(app.state.database, app.state.settings)
    await reconcile_journal_jobs(app.state.database, app.state.settings)
    assert len(await jobs(app)) == 25


async def test_model_change_cancels_and_reembeds_without_mixing(journal_configured):
    app, actors = journal_configured
    await create(actors[0][0])
    app.state.settings.voyage_model = "synthetic-v2"
    await reconcile_journal_jobs(app.state.database, app.state.settings)
    await due(app)
    fake = FakeEmbedder(256)
    await tick(app, fake)
    assert [v.model for v in await vectors(app)] == ["synthetic-v2"]
    assert any(j.status == "cancelled" and j.model == "synthetic" for j in await jobs(app))


@pytest.mark.parametrize("invalid", ["missing", "future", "too_young", "wrong_policy"])
async def test_ineligible_legacy_entries_cannot_starve_valid_backfill(journal_configured, invalid):
    from app.infrastructure.database.models import AgeDeclaration

    app, actors = journal_configured
    app.state.settings.embedding_job_batch_size = 1
    async with app.state.database.sessions.begin() as db:
        declaration = await db.get(AgeDeclaration, actors[1][1])
        if invalid == "missing":
            await db.delete(declaration)
        elif invalid == "future":
            declaration.declared_at = now()+timedelta(days=1)
        elif invalid == "too_young":
            declaration.birth_year = now().year-17
        else:
            declaration.policy_version = "invalid-policy"
        for identity, uid in ((1, actors[1][1]), (2, actors[0][1])):
            db.add(JournalEntry(id=UUID(int=identity), user_id=uid, local_date=today(), timezone="Asia/Bangkok",
                                mood=3, text="Dữ liệu backfill tổng hợp", status="saved"))
    assert await reconcile_journal_jobs(app.state.database, app.state.settings) == 1
    assert [job.user_id for job in await jobs(app)] == [actors[0][1]]


def test_document_is_bounded_and_hash_stable():
    row = JournalEntry(local_date=today(), mood=3, text="x"*10000, emotions=["vui"], factors=["vẽ"])
    document = journal_document(row)
    assert len(document) <= 7100
    assert hashlib.sha256(document.encode()).hexdigest() == hashlib.sha256(journal_document(row).encode()).hexdigest()
    assert str(uuid4()) not in document
