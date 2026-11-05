"""Independent final-review regressions: financial fences, queued dispatch and live leases."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from tests.guest_helpers import LIFETIME, db_now
from tests.test_guest_budget import reserve, run, today_row
from tests.test_guest_embeddings import PausedProvider, queue, semantic_guest

pytestmark = pytest.mark.postgres


async def test_concurrent_settlement_refreshes_preloaded_reservation(clients):
    from app.modules.guests.accounting import mark_guest_dispatched, settle_guest_operation
    from app.modules.guests.models import GuestBudgetDay, GuestCostReservation
    from tests.guest_helpers import add_guest

    app, _ = clients
    guest = await add_guest(app)
    reservation = await reserve(app, guest, 300)
    await reserve(app, guest, 600)
    await run(app, lambda db: mark_guest_dispatched(db, reservation.id))
    waiting = asyncio.Event()
    async with app.state.database.sessions() as first, first.begin():
        await first.scalar(select(GuestBudgetDay).with_for_update())

        async def competing():
            async with app.state.database.sessions.begin() as second:
                cached = await second.get(GuestCostReservation, reservation.id)
                assert cached.state == "dispatched"
                waiting.set()
                await settle_guest_operation(second, reservation, None)
        task = asyncio.create_task(competing())
        await waiting.wait()
        await asyncio.sleep(0.1)
        await settle_guest_operation(first, reservation, None)
    await asyncio.wait_for(task, 5)
    day = await today_row(app)
    assert (day.spent_nano_usd, day.reserved_nano_usd) == (300, 600)


@pytest.mark.parametrize("terminal", ["cancelled", "uncertain"])
async def test_terminal_reservation_cannot_authorize_provider_dispatch(clients, terminal):
    from app.core.errors import DomainError
    from app.modules.guests.accounting import (
        mark_guest_dispatched,
        release_guest_operation,
        settle_guest_operation,
    )
    from tests.guest_helpers import add_guest
    app, _ = clients
    reservation = await reserve(app, await add_guest(app), 300)
    if terminal == "cancelled":
        await run(app, lambda db: release_guest_operation(db, reservation.id))
    else:
        await run(app, lambda db: settle_guest_operation(db, reservation, None))
    with pytest.raises(DomainError):
        await run(app, lambda db: mark_guest_dispatched(db, reservation.id))


async def test_document_embedding_never_dispatches_after_admission_crosses_expiry(clients, monkeypatch):
    from app.ai import embeddings
    app, _ = clients
    guest, settings, memory = await semantic_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    await queue(app, settings, memory)
    original = embeddings._guest_embed_admission
    async def delayed(*args):
        result = await original(*args)
        await asyncio.sleep(max(0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.1)
        return result
    monkeypatch.setattr(embeddings, "_guest_embed_admission", delayed)
    provider = PausedProvider()
    provider.release.set()
    await embeddings.process_embedding_jobs(app.state.database, settings, provider)
    assert provider.calls == [], "private memory must not be sent after T"


async def test_document_provider_is_cancelled_at_guest_deadline(clients):
    from app.ai.embeddings import process_embedding_jobs
    app, _ = clients
    guest, settings, memory = await semantic_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    await queue(app, settings, memory)
    provider = PausedProvider()
    task = asyncio.create_task(process_embedding_jobs(app.state.database, settings, provider))
    await asyncio.wait_for(provider.started.wait(), 5)
    try:
        await asyncio.sleep(max(0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.25)
        assert task.done(), "guest worker must stop waiting on provider at T"
    finally:
        provider.release.set()
        await task


@pytest.mark.parametrize("closed", ["flag", "price", "budget"])
async def test_guest_query_embedding_needs_its_own_funded_admission(clients, closed):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.core.security import Actor
    app, _ = clients
    guest, settings, memory = await semantic_guest(app, started_ago=timedelta(minutes=1))
    await queue(app, settings, memory)
    index = PausedProvider()
    index.release.set()
    await process_embedding_jobs(app.state.database, settings, index)
    assert index.calls, "precondition: an indexed guest memory exists before closing the adapter"
    if closed == "flag":
        settings.guest_semantic_enabled = False
    elif closed == "price":
        settings.guest_pricing_json = {k: v for k, v in settings.guest_pricing_json.items() if k != "embed"}
    else:
        settings.guest_daily_budget_usd = 0
    provider = PausedProvider()
    provider.release.set()
    result = await retrieve_memories(app.state.database, settings, Actor(guest.user_id, guest.session_id, 1, "guest"), "may", "đọc sách", 1, provider=provider)
    assert provider.calls == [], "query embeddings are separately paid, not covered by model token reservation"
    assert result == ["Tôi thích đọc sách"], "lexical fallback preserves approved memory without an external call"


async def test_funded_query_embedding_is_charged_once_without_consuming_a_document_slot(clients):
    from app.ai.embeddings import process_embedding_jobs, retrieve_memories
    from app.core.security import Actor
    from app.modules.guests.models import GuestUsage
    app, _ = clients
    guest, settings, memory = await semantic_guest(app, started_ago=timedelta(minutes=1))
    await queue(app, settings, memory)
    provider = PausedProvider()
    provider.release.set()
    await process_embedding_jobs(app.state.database, settings, provider)
    assert len(provider.calls) == 1
    actor = Actor(guest.user_id, guest.session_id, 1, "guest")
    for _ in range(2):
        assert await retrieve_memories(app.state.database, settings, actor, "may", "đọc sách", 1,
            provider=provider, operation_key="query-replay") == ["Tôi thích đọc sách"]
    assert [kind for _, kind in provider.calls] == ["document", "query"]
    assert (await today_row(app)).spent_nano_usd == 22
    async with app.state.database.sessions() as db:
        assert (await db.get(GuestUsage, guest.user_id)).semantic_memories == 1


async def test_active_ai_claim_is_renewed_while_a_long_provider_call_is_pending(clients, monkeypatch):
    from app.modules.guests import limits
    from app.modules.guests.models import GuestOperationLink
    from tests.fakes import ScriptedModel, message_output
    from tests.guest_helpers import add_guest
    from tests.test_guest_inflight import start_guest_run
    monkeypatch.setattr(limits, "QUOTA_LEASE_SECONDS", 1)
    monkeypatch.setattr(limits, "QUOTA_HEARTBEAT_SECONDS", 0.1, raising=False)
    app, _ = clients
    guest = await add_guest(app)
    model = ScriptedModel([[message_output('{"text":"synthetic","cards":[]}')]], hold=True)
    await start_guest_run(app, guest, model)
    await asyncio.wait_for(model.started.wait(), 5)
    try:
        await asyncio.sleep(1.3)
        async with app.state.database.sessions() as db:
            claim = await db.scalar(select(GuestOperationLink).where(GuestOperationLink.user_id == guest.user_id))
        assert claim.lease_until > await db_now(app), "an active run must retain its global/per-user slot"
    finally:
        model.release.set()


async def test_voice_claim_is_renewed_until_the_preview_provider_finishes(clients, monkeypatch):
    from app.modules.guests import limits
    from app.modules.guests.models import GuestOperationLink
    from tests.guest_helpers import add_guest, enable_paid_fixture
    from tests.test_voice import audio
    monkeypatch.setattr(limits, "QUOTA_LEASE_SECONDS", 1)
    monkeypatch.setattr(limits, "QUOTA_HEARTBEAT_SECONDS", 0.1)
    app, _ = clients
    enable_paid_fixture(app)
    guest = await add_guest(app, consents=True)
    started, release = asyncio.Event(), asyncio.Event()
    class Voice:
        async def transcribe(self, data):
            started.set()
            await release.wait()
            return "synthetic preview"
    app.state.transcriber = Voice()
    task = asyncio.create_task(guest.client.post("/api/v1/voice/transcriptions", content=audio(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": "held-voice"}))
    await asyncio.wait_for(started.wait(), 5)
    try:
        await asyncio.sleep(1.3)
        async with app.state.database.sessions() as db:
            claim = await db.scalar(select(GuestOperationLink).where(GuestOperationLink.user_id == guest.user_id))
        assert claim.lease_until > await db_now(app)
    finally:
        release.set()
        assert (await task).status_code == 200


async def test_heartbeat_never_revives_a_stolen_claim(clients, monkeypatch):
    from sqlalchemy import update

    from app.core.errors import DomainError
    from app.modules.guests import limits
    from app.modules.guests.models import GuestOperationLink
    from tests.guest_helpers import add_guest
    from tests.test_guest_quotas import claim
    monkeypatch.setattr(limits, "QUOTA_HEARTBEAT_SECONDS", 0.05)
    app, _ = clients
    guest = await add_guest(app)
    ticket = await claim(app, guest)
    started = asyncio.Event()
    async def held():
        async with limits.maintain_guest_quota(app.state.database, guest.user_id, "ai", ticket):
            started.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(held())
    await started.wait()
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(GuestOperationLink).where(GuestOperationLink.user_id == guest.user_id).values(lease_token=__import__("uuid").uuid4()))
    with pytest.raises(DomainError, match="GUEST_OPERATION_FENCED"):
        await asyncio.wait_for(task, 2)


async def test_blocked_heartbeat_cancels_work_before_its_existing_lease_expires(clients, monkeypatch):
    from app.core.errors import DomainError
    from app.modules.guests import limits
    from tests.guest_helpers import add_guest
    from tests.test_guest_quotas import claim
    monkeypatch.setattr(limits, "QUOTA_LEASE_SECONDS", 1)
    monkeypatch.setattr(limits, "QUOTA_HEARTBEAT_SECONDS", 0.05)
    app, _ = clients
    guest = await add_guest(app)
    ticket = await claim(app, guest)
    original = limits.renew_guest_quota
    calls = 0
    async def blocked(*args):
        nonlocal calls
        calls += 1
        if calls > 1:
            await asyncio.Event().wait()  # renewal waits on an unavailable DB/owner lock
        return await original(*args)
    monkeypatch.setattr(limits, "renew_guest_quota", blocked)
    async def held():
        async with limits.maintain_guest_quota(app.state.database, guest.user_id, "ai", ticket):
            await asyncio.Event().wait()
    with pytest.raises(DomainError, match="GUEST_OPERATION_FENCED"):
        await asyncio.wait_for(held(), 2)
