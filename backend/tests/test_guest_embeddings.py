"""Guest memory/history lifetime caps and embedding publication fences (GE-05.3)."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from tests.guest_helpers import PAID_PRICING, add_guest, db_now, enable_paid_fixture

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)


class PausedProvider:
    """Synthetic embedding provider that waits for the test before it answers."""

    def __init__(self):
        self.calls, self.started, self.release = [], asyncio.Event(), asyncio.Event()

    async def embed(self, text, input_type):
        self.calls.append((text, input_type))
        self.started.set()
        await self.release.wait()
        return [1.0] + [0.0] * 255


async def semantic_guest(app, *, started_ago, flag=True):
    from app.ai.models import AiPreference
    from app.core.config import Settings
    from app.infrastructure.database.models import Consent, Memory

    guest = await add_guest(app, started_ago=started_ago)
    settings = Settings(
        _env_file=None,
        semantic_memory_enabled=True,
        voyage_api_key="synthetic",
        voyage_dimensions=256,
        guest_semantic_enabled=flag,
        guest_paid_enabled=True,
        guest_daily_budget_usd="0.01",
        guest_pricing_json=PAID_PRICING,
    )
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(Consent)
            .where(Consent.user_id == guest.user_id, Consent.purpose.in_(("AI", "MEM")))
            .values(enabled=True)
        )
        db.add(
            AiPreference(
                user_id=guest.user_id, semantic_memory_enabled=True, policy_version="ai-data-v1"
            )
        )
        memory = Memory(
            user_id=guest.user_id, bot_id="may", text="Tôi thích đọc sách", proposal_id=uuid4()
        )
        db.add(memory)
        await db.flush()
        memory_id = memory.id
    return guest, settings, memory_id


async def queue(app, settings, memory_id):
    from app.ai.embeddings import enqueue_memory
    from app.infrastructure.database.models import Memory

    async with app.state.database.sessions.begin() as db:
        await enqueue_memory(db, await db.get(Memory, memory_id), settings)


async def counts(app):
    from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding

    async with app.state.database.sessions() as db:
        return (
            await db.scalar(select(func.count()).select_from(MemoryEmbedding)),
            await db.scalar(select(func.count()).select_from(EmbeddingJob)),
        )


async def test_late_embedding_cannot_recreate_deleted_memory(clients):
    from app.ai.embedding_models import EmbeddingJob
    from app.ai.embeddings import process_embedding_jobs, reconcile_embedding_jobs

    app, _ = clients
    guest, settings, memory_id = await semantic_guest(
        app, started_ago=LIFETIME - timedelta(seconds=3)
    )
    await queue(app, settings, memory_id)
    assert await counts(app) == (0, 1)
    provider = PausedProvider()
    worker = asyncio.create_task(process_embedding_jobs(app.state.database, settings, provider))
    await asyncio.wait_for(provider.started.wait(), 5)

    # The job was claimed and validated before T; the provider answers only after T.
    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.3)
    provider.release.set()
    await asyncio.wait_for(worker, 5)
    assert (await counts(app))[0] == 0, "no vector may be published after the deadline"
    async with app.state.database.sessions() as db:
        job = await db.scalar(select(EmbeddingJob))
    assert job.status == "cancelled", "the expired job is removed from work, never retried"
    assert job.lease_token is None

    # Reconciliation never recreates work for an expired guest.
    assert await reconcile_embedding_jobs(app.state.database, settings) == 0
    assert await process_embedding_jobs(app.state.database, settings, PausedProvider()) == 0
    assert await counts(app) == (0, 1)


async def test_expired_guest_memory_cannot_be_enqueued(clients):
    app, _ = clients
    guest, settings, memory_id = await semantic_guest(
        app, started_ago=LIFETIME + timedelta(seconds=5)
    )
    await queue(app, settings, memory_id)
    assert await counts(app) == (0, 0)


async def test_guest_semantic_memory_needs_its_own_rollout_flag(clients):
    app, _ = clients
    off, settings_off, off_memory = await semantic_guest(app, started_ago=timedelta(minutes=1), flag=False)
    await queue(app, settings_off, off_memory)
    assert await counts(app) == (0, 0), "GUEST_SEMANTIC_ENABLED defaults off"
    on, settings_on, on_memory = await semantic_guest(app, started_ago=timedelta(minutes=1), flag=True)
    await queue(app, settings_on, on_memory)
    assert await counts(app) == (0, 1)


async def test_guest_proposal_and_history_expiry_capped(clients):
    from app.ai.memory import create_proposal
    from app.ai.models import AiConversation, AiPreference
    from app.core.errors import DomainError
    from app.core.security import Actor
    from app.infrastructure.database.models import User
    from tests.fakes import make_test_model

    app, _ = clients
    app.state.ai.model_override = make_test_model("x")
    enable_paid_fixture(app)
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(minutes=5), consents=True)
    actor = Actor(guest.user_id, guest.session_id, 1, "guest")
    async with app.state.database.sessions.begin() as db:
        data_version = (await db.get(User, guest.user_id)).data_version
        proposal = await create_proposal(db, actor, "may", "Tôi thích đi bộ", data_version)
        proposed_until = proposal.expires_at
    assert proposed_until <= guest.expires_at, "a 15-minute preview never outlives a 5-minute trial"

    # A saved conversation (history is opt-in) expires with the trial, never after it.
    async with app.state.database.sessions.begin() as db:
        db.add(AiPreference(user_id=guest.user_id, history_enabled=True, semantic_memory_enabled=False, version=1))
    created = await guest.client.post(
        "/api/v1/ai/conversations",
        json={"botId": "may"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert created.status_code == 201, created.text
    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiConversation).where(AiConversation.user_id == guest.user_id))).all()
    assert rows and all(row.expires_at <= guest.expires_at for row in rows)

    # At the deadline a proposal can no longer be created or approved.
    late = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=2), consents=True)
    async with app.state.database.sessions.begin() as db:
        with pytest.raises(DomainError) as denied:
            await create_proposal(
                db, Actor(late.user_id, late.session_id, 1, "guest"), "may", "x", 1
            )
    assert denied.value.code == "GUEST_EXPIRED"
