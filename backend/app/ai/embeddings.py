"""Derived approved-memory indexing. All authorization stays in PostgreSQL predicates."""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Float, and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.ai.embedding_config import EmbeddingSettings
from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
from app.ai.models import AiPreference
from app.ai.voyage import EmbeddingError, EmbeddingProvider, VoyageProvider, validate_vector
from app.core.security import Actor, lock_actor
from app.infrastructure.database.models import Consent, Memory, PrivateItem, User, now
from app.modules.guests.policy import database_time, lifetime_allows

if TYPE_CHECKING:
    from app.infrastructure.database.connection import Database

MEMORY_BOTS = ("may", "guong", "nhip", "rure")
# Operational counters only: never memory text, owner IDs or job IDs.
log = logging.getLogger("moodprint.embeddings")


@dataclass(frozen=True)
class Authorization:
    data_version: int
    preference_version: int
    ai_consent_version: int
    mem_consent_version: int
    semantic: bool


async def _authorization(db: AsyncSession, user_id: UUID) -> Authorization | None:
    # Every mutation uses the same owner lock. No provider call holds this lock.
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if (
        not user
        or user.status != "active"
        or user.deletion_pending
        or user.age_band not in ("teen", "adult")
    ):
        return None
    if user.account_kind == "guest" and not lifetime_allows(user, await database_time(db)):
        # Owner lock + fresh database clock: an expired guest never authorizes publication.
        return None
    consents = {
        c.purpose: c
        for c in (
            await db.scalars(
                select(Consent).where(
                    Consent.user_id == user_id, Consent.purpose.in_(("AI", "MEM"))
                )
            )
        ).all()
    }
    if any(
        p not in consents or not consents[p].enabled or consents[p].policy_version != "v1"
        for p in ("AI", "MEM")
    ):
        return None
    pref = await db.get(AiPreference, user_id)
    return Authorization(
        user.data_version,
        pref.version if pref else 0,
        consents["AI"].version,
        consents["MEM"].version,
        bool(pref and pref.semantic_memory_enabled and pref.policy_version == "ai-data-v1"),
    )


def _current_source():
    return or_(
        Memory.source_id.is_(None),
        exists(
            select(PrivateItem.id).where(
                PrivateItem.id == Memory.source_id,
                PrivateItem.user_id == Memory.user_id,
                PrivateItem.status == "confirmed",
                PrivateItem.version == Memory.source_version,
            )
        ),
    )


def _memory_scope(user_id: UUID, bot_id: str):
    return (
        Memory.user_id == user_id,
        Memory.bot_id == bot_id,
        Memory.status == "active",
        _current_source(),
    )


def _snapshot(auth: Authorization) -> dict:
    # An unrelated profile/mood edit increments global data_version. It must not
    # cause every unchanged approved memory to be sent to the provider again.
    return {
        "preference_version": auth.preference_version,
        "ai_consent_version": auth.ai_consent_version,
        "mem_consent_version": auth.mem_consent_version,
    }


async def enqueue_memory(db: AsyncSession, memory: Memory, settings: EmbeddingSettings) -> None:
    if not settings.semantic_memory_available or memory.bot_id not in MEMORY_BOTS:
        return
    await db.flush()
    auth = await _authorization(db, memory.user_id)
    owner = await db.get(User, memory.user_id)
    if owner is not None and owner.account_kind == "guest" and not getattr(
        settings, "guest_semantic_enabled", False
    ):
        return
    if (
        not auth
        or not auth.semantic
        or not await db.scalar(
            select(Memory.id).where(
                Memory.id == memory.id, *_memory_scope(memory.user_id, memory.bot_id)
            )
        )
    ):
        return
    await db.execute(
        insert(EmbeddingJob)
        .values(
            memory_id=memory.id,
            user_id=memory.user_id,
            bot_id=memory.bot_id,
            memory_version=memory.version,
            data_version=auth.data_version,
            **_snapshot(auth),
            model=settings.voyage_model,
            dimensions=settings.voyage_dimensions,
        )
        .on_conflict_do_update(
            constraint="uq_memory_embedding_jobs_snapshot",
            set_={
                "status": "pending",
                "attempts": 0,
                "available_at": now(),
                "lease_token": None,
                "lease_until": None,
                "last_error": None,
            },
            where=EmbeddingJob.status == "cancelled",
        )
    )


async def invalidate_memory(db: AsyncSession, memory_id: UUID) -> None:
    await db.execute(delete(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id))
    await db.execute(
        update(EmbeddingJob)
        .where(
            EmbeddingJob.memory_id == memory_id,
            EmbeddingJob.status.in_(("pending", "retry", "running")),
        )
        .values(status="cancelled", lease_token=None, lease_until=None)
    )


async def discard_user_index(db: AsyncSession, user_id: UUID) -> None:
    """Drop derived vectors and stop queued work after opt-out or consent withdrawal.

    Snapshots are consent-versioned, so these rows could never be used again; deleting
    them keeps no orphaned private derivatives. Reconciliation re-indexes on re-grant.
    """
    await db.execute(delete(MemoryEmbedding).where(MemoryEmbedding.user_id == user_id))
    await db.execute(
        update(EmbeddingJob)
        .where(
            EmbeddingJob.user_id == user_id,
            EmbeddingJob.status.in_(("pending", "running", "retry")),
        )
        .values(status="cancelled", lease_token=None, lease_until=None)
    )


async def _job_memory(db: AsyncSession, job: EmbeddingJob) -> Memory | None:
    auth = await _authorization(db, job.user_id)
    if (
        not auth
        or not auth.semantic
        or _snapshot(auth) != {k: getattr(job, k) for k in _snapshot(auth)}
    ):
        return None
    return await db.scalar(
        select(Memory).where(
            Memory.id == job.memory_id,
            Memory.version == job.memory_version,
            *_memory_scope(job.user_id, job.bot_id),
        )
    )


async def reconcile_embedding_jobs(database: "Database", settings: EmbeddingSettings) -> int:
    """Find bounded missing current snapshots; existing/failed jobs cannot starve later rows."""
    if not settings.semantic_memory_available:
        return 0
    ai, mem = aliased(Consent), aliased(Consent)
    async with database.require()() as db, db.begin():
        missing = ~exists(
            select(EmbeddingJob.id).where(
                EmbeddingJob.memory_id == Memory.id,
                EmbeddingJob.memory_version == Memory.version,
                EmbeddingJob.model == settings.voyage_model,
                EmbeddingJob.dimensions == settings.voyage_dimensions,
                EmbeddingJob.preference_version == AiPreference.version,
                EmbeddingJob.ai_consent_version == ai.version,
                EmbeddingJob.mem_consent_version == mem.version,
                EmbeddingJob.status != "cancelled",
            )
        )
        ids = list(
            (
                await db.scalars(
                    select(Memory.id)
                    .join(User, User.id == Memory.user_id)
                    .join(AiPreference, AiPreference.user_id == User.id)
                    .join(ai, and_(ai.user_id == User.id, ai.purpose == "AI"))
                    .join(mem, and_(mem.user_id == User.id, mem.purpose == "MEM"))
                    .where(
                        User.status == "active",
                        User.deletion_pending.is_(False),
                        User.age_band.in_(("teen", "adult")),
                        or_(
                            User.account_kind == "registered",
                            User.guest_expires_at > func.clock_timestamp(),
                        ),
                        AiPreference.semantic_memory_enabled.is_(True),
                        AiPreference.policy_version == "ai-data-v1",
                        ai.enabled.is_(True),
                        mem.enabled.is_(True),
                        ai.policy_version == "v1",
                        mem.policy_version == "v1",
                        Memory.status == "active",
                        Memory.bot_id.in_(MEMORY_BOTS),
                        _current_source(),
                        missing,
                    )
                    .order_by(Memory.id)
                    .limit(settings.embedding_job_batch_size)
                )
            ).all()
        )
    # Separate short owner transactions avoid holding many account locks at once.
    for memory_id in ids:
        async with database.require()() as db, db.begin():
            memory = await db.get(Memory, memory_id)
            if memory:
                await enqueue_memory(db, memory, settings)
    return len(ids)


async def process_embedding_jobs(
    database: "Database", settings: EmbeddingSettings, provider: EmbeddingProvider | None = None
) -> int:
    """One bounded worker tick; SKIP LOCKED, expiring leases, and fenced publication."""
    if not settings.semantic_memory_available:
        return 0
    await reconcile_embedding_jobs(database, settings)
    provider = provider or VoyageProvider(settings)
    processed = 0
    for _ in range(settings.embedding_job_batch_size):
        # Claim only the job row here, then release it before locking the owner.
        # This avoids an owner/job lock inversion with memory lifecycle mutations.
        async with database.require()() as db, db.begin():
            job = await db.scalar(
                select(EmbeddingJob)
                .where(
                    or_(
                        and_(
                            EmbeddingJob.status.in_(("pending", "retry")),
                            EmbeddingJob.available_at <= now(),
                        ),
                        and_(EmbeddingJob.status == "running", EmbeddingJob.lease_until <= now()),
                    ),
                )
                .order_by(EmbeddingJob.available_at, EmbeddingJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if not job:
                break
            if job.model != settings.voyage_model or job.dimensions != settings.voyage_dimensions:
                job.status, job.lease_token, job.lease_until = "cancelled", None, None
                continue
            if job.attempts >= settings.embedding_max_attempts:
                job.status = "failed"
                job.lease_token = None
                job.lease_until = None
                continue
            job.status, job.lease_token = "running", uuid4()
            job.lease_until = now() + timedelta(seconds=settings.embedding_lease_seconds)
            job.attempts += 1
            job_id, user_id, token = job.id, job.user_id, job.lease_token
        async with database.require()() as db, db.begin():
            # Consistent owner -> job order in validation/publication transactions.
            await db.scalar(select(User.id).where(User.id == user_id).with_for_update())
            job = await db.get(EmbeddingJob, job_id, with_for_update=True)
            if not job or job.status != "running" or job.lease_token != token:
                continue
            memory = await _job_memory(db, job)
            if not memory:
                job.status, job.lease_token, job.lease_until = "cancelled", None, None
                continue
            text = memory.text
        error: str | None = None
        vector: list[float] = []
        try:
            vector = validate_vector(
                await provider.embed(text, "document"), settings.voyage_dimensions
            )
        except EmbeddingError as exc:
            # Codes are controlled internally; never persist arbitrary exception content.
            error = (
                str(exc)
                if str(exc)
                in (
                    "embedding_provider_unavailable",
                    "embedding_invalid_response",
                    "embedding_invalid_vector",
                    "embedding_unconfigured",
                    "embedding_input_invalid",
                )
                else "embedding_provider_unavailable"
            )
        except Exception:
            error = "embedding_provider_unavailable"
        async with database.require()() as db, db.begin():
            await db.scalar(select(User.id).where(User.id == user_id).with_for_update())
            job = await db.get(EmbeddingJob, job_id, with_for_update=True)
            if (
                not job
                or job.status != "running"
                or job.lease_token != token
                or not job.lease_until
                or job.lease_until <= now()
            ):
                continue
            memory = await _job_memory(db, job)
            if not memory:
                job.status = "cancelled"
            elif error:
                job.status = (
                    "failed" if job.attempts >= settings.embedding_max_attempts else "retry"
                )
                job.last_error = error
                job.available_at = now() + timedelta(seconds=min(3600, 5 * 2 ** (job.attempts - 1)))
            else:
                values = {
                    k: getattr(job, k)
                    for k in (
                        "memory_id",
                        "user_id",
                        "bot_id",
                        "memory_version",
                        "data_version",
                        "preference_version",
                        "ai_consent_version",
                        "mem_consent_version",
                        "model",
                        "dimensions",
                    )
                }
                values.update(embedding=vector, created_at=now())
                await db.execute(
                    insert(MemoryEmbedding)
                    .values(**values)
                    .on_conflict_do_update(constraint="uq_memory_embeddings_config", set_=values)
                )
                job.status, job.last_error = "succeeded", None
            job.lease_token, job.lease_until = None, None
            log.info(
                "embedding_job_attempt state=%s attempt=%s error=%s",
                job.status,
                job.attempts,
                job.last_error if job.status != "succeeded" else "none",
            )
        processed += 1
    if processed:
        await _log_queue_state(database)
    return processed


async def _log_queue_state(database: "Database") -> None:
    async with database.require()() as db:
        counts = dict(
            (
                await db.execute(
                    select(EmbeddingJob.status, func.count())
                    .where(EmbeddingJob.status.in_(("pending", "running", "retry", "failed")))
                    .group_by(EmbeddingJob.status)
                )
            ).all()
        )
    log.info(
        "embedding_queue_state pending=%s running=%s retry=%s failed=%s",
        *(counts.get(state, 0) for state in ("pending", "running", "retry", "failed")),
    )


def _indexed_scope(user_id: UUID, bot_id: str, auth: Authorization, settings: EmbeddingSettings):
    return (
        MemoryEmbedding.user_id == user_id,
        MemoryEmbedding.bot_id == bot_id,
        MemoryEmbedding.memory_id == Memory.id,
        MemoryEmbedding.memory_version == Memory.version,
        MemoryEmbedding.model == settings.voyage_model,
        MemoryEmbedding.dimensions == settings.voyage_dimensions,
        *(getattr(MemoryEmbedding, key) == value for key, value in _snapshot(auth).items()),
        *_memory_scope(user_id, bot_id),
    )


def _bounded(texts: list[str], settings: EmbeddingSettings) -> list[str]:
    result: list[str] = []
    remaining = settings.memory_context_char_limit
    for value in texts[: settings.memory_retrieval_limit]:
        if len(value) <= remaining:
            result.append(value)
            remaining -= len(value)
    return result


async def _fallback(
    db: AsyncSession, user_id: UUID, bot_id: str, query: str, settings: EmbeddingSettings
) -> list[str]:
    rows = (
        await db.execute(
            select(Memory.id, Memory.text)
            .where(*_memory_scope(user_id, bot_id))
            .order_by(Memory.version.desc(), Memory.id)
            .limit(settings.memory_fallback_limit)
        )
    ).all()
    return _bounded(
        lexical_rank([(row.id, row.text) for row in rows], query, settings.memory_retrieval_limit),
        settings,
    )


async def retrieve_memories(
    database: "Database",
    settings: EmbeddingSettings,
    actor: Actor,
    bot_id: str,
    query: str,
    data_version: int,
    *,
    provider: EmbeddingProvider | None = None,
) -> list[str]:
    if bot_id not in MEMORY_BOTS:
        return []
    async with database.require()() as db, db.begin():
        await lock_actor(db, actor)
        auth = await _authorization(db, actor.user_id)
        if not auth or auth.data_version != data_version:
            return []
        if not auth.semantic or not settings.semantic_memory_available or not query.strip():
            return await _fallback(db, actor.user_id, bot_id, query, settings)
        indexed = await db.scalar(
            select(MemoryEmbedding.id)
            .join(Memory, Memory.id == MemoryEmbedding.memory_id)
            .where(*_indexed_scope(actor.user_id, bot_id, auth, settings))
            .limit(1)
        )
        if not indexed:
            return await _fallback(db, actor.user_id, bot_id, query, settings)
    try:
        vector = validate_vector(
            await (provider or VoyageProvider(settings)).embed(query[:8000], "query"),
            settings.voyage_dimensions,
        )
    except Exception:
        vector = []
    async with database.require()() as db, db.begin():
        await lock_actor(db, actor)
        current = await _authorization(db, actor.user_id)
        if current != auth:
            return []
        if not vector:
            return await _fallback(db, actor.user_id, bot_id, query, settings)
        # Exact cosine over authorized rows. No approximate index can prefilter away
        # an owner's eligible results; model/dimensions never mix in the operator.
        distance = MemoryEmbedding.embedding.op("OPERATOR(extensions.<=>)", return_type=Float)(
            vector
        )
        rows = (
            (
                await db.execute(
                    select(Memory.text)
                    .join(MemoryEmbedding, MemoryEmbedding.memory_id == Memory.id)
                    .where(
                        *_indexed_scope(actor.user_id, bot_id, auth, settings),
                        distance <= 1 - settings.memory_similarity_threshold,
                    )
                    .order_by(distance, Memory.id)
                    .limit(settings.memory_retrieval_limit)
                )
            )
            .scalars()
            .all()
        )
        return _bounded(list(rows), settings)


def lexical_rank(rows: list[tuple[UUID, str]], query: str, limit: int) -> list[str]:
    """Stable current-revision input order breaks ties; never invent personal facts."""

    def tokens(value: str) -> set[str]:
        return set(re.findall(r"\w+", unicodedata.normalize("NFC", value).casefold()))

    terms = tokens(query)
    ranked = sorted(enumerate(rows), key=lambda row: (-len(terms & tokens(row[1][1])), row[0]))
    return [row[1][1] for row in ranked[:limit]]
