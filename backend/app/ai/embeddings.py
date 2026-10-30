"""Derived approved-memory indexing. All authorization stays in PostgreSQL predicates."""

import asyncio
import hashlib
import logging
import re
import time
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
from app.core.errors import DomainError
from app.core.security import Actor, lock_actor
from app.infrastructure.database.models import Consent, Memory, User, now
from app.modules.consent.policy import consent_enabled
from app.modules.guests.deadlines import guest_deadline
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
        p not in consents or not consent_enabled(p, consents[p].enabled) or consents[p].policy_version != "v1"
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


def _memory_scope(user_id: UUID, bot_id: str):
    return (
        Memory.user_id == user_id,
        Memory.bot_id == bot_id,
        Memory.status == "active",
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


async def _guest_embed_admission(db: AsyncSession, owner: User, job: EmbeddingJob, settings):
    """Quota claim + worst-case reservation for one guest embedding, or None (never raises)."""
    return await _guest_embedding_ticket(db, owner, settings, key=f"embed:{job.id}",
        payload=f"{job.memory_id}:{job.memory_version}", document=True)


async def _guest_embedding_ticket(db, owner, settings, *, key: str, payload: str, document: bool):
    from app.modules.guests.accounting import reserve_guest_operation
    from app.modules.guests.limits import reserve_guest_quota
    from app.modules.guests.policy import guest_paid_available
    from app.modules.guests.pricing import budget_nano, embed_upper

    if not (getattr(settings, "guest_semantic_enabled", False) and guest_paid_available(settings, "embed")):
        return None
    upper = embed_upper(settings.guest_pricing_json)
    if upper is None:
        return None
    try:
        async with db.begin_nested():
            quota = await reserve_guest_quota(
                db, owner, kind="embed", operation_key=key, payload_digest=payload, settings=settings,
                semantic_document=document,
            )
            reservation = await reserve_guest_operation(
                db,
                owner,
                "embed",
                upper[1],
                operation_key=key,
                payload_digest=payload,
                limit_nano_usd=budget_nano(settings.guest_daily_budget_usd) or 0,
            )
    except DomainError:
        return None
    from app.modules.guests.models import GuestCostReservation

    row = await db.get(GuestCostReservation, reservation.id)
    if row is None or row.state != "reserved":
        return None  # a replayed key can never fund a second paid dispatch
    return quota, reservation


async def _settle_guest_embed(database: "Database", user_id: UUID, ticket, *, known: bool, dispatched: bool = True) -> None:
    from app.modules.guests.accounting import release_guest_operation, settle_guest_operation
    from app.modules.guests.limits import finish_guest_quota

    quota, reservation = ticket
    try:
        async with database.require()() as db, db.begin():
            if dispatched:
                await settle_guest_operation(db, reservation, reservation.upper_nano_usd if known else None)
            else:
                await release_guest_operation(db, reservation.id)
        async with database.require()() as db, db.begin():
            await finish_guest_quota(db, user_id, "embed", quota.operation_key_hash, quota.lease_token)
    except Exception:  # the stale-reservation sweep charges it uncertain
        log.warning("guest_embed_settlement_deferred")


async def _document_dispatch(db, settings, user_id, document_job: tuple[UUID, UUID]):
    """Owner is locked first; job/resource checks linearize the document send.

    Mutations committed before this decision must deny. The commit releases locks
    before provider I/O; later invalidation cannot recall an accepted external send.
    """
    job_id, token = document_job
    job = await db.get(EmbeddingJob, job_id, with_for_update=True, populate_existing=True)
    before = time.monotonic()
    at = await database_time(db)
    if (job is None or job.user_id != user_id or job.status != "running"
            or job.lease_token != token or job.lease_until is None or job.lease_until <= at
            or job.model != settings.voyage_model or job.dimensions != settings.voyage_dimensions):
        raise EmbeddingError("embedding_unconfigured")
    memory = await _job_memory(db, job)
    if memory is None:
        raise EmbeddingError("embedding_unconfigured")
    return memory.text, before + (job.lease_until - at).total_seconds()


async def _guest_embedding_call(database, settings, provider, user_id, ticket, value, input_type, expected,
                                *, document_job: tuple[UUID, UUID] | None = None):
    """Fund guest queries/documents; fence every document, including registered work."""
    from app.modules.guests.accounting import mark_guest_dispatched
    from app.modules.guests.limits import maintain_guest_quota
    from app.modules.guests.models import GuestOperationLink
    from app.modules.guests.policy import guest_expired, guest_paid_available
    dispatched = known = False
    try:
        if input_type == "document" and document_job is None:
            raise EmbeddingError("embedding_unconfigured")
        async with maintain_guest_quota(database, user_id, "embed", ticket[0] if ticket else None):
            async with database.require()() as db, db.begin():
                current = await _authorization(db, user_id)
                if current is None or not current.semantic or _snapshot(current) != expected:
                    raise EmbeddingError("embedding_unconfigured")
                owner = await db.get(User, user_id)
                if document_job is not None:
                    # Canonical owner -> job -> budget/reservation -> resource ordering.
                    await db.get(EmbeddingJob, document_job[0], with_for_update=True)
                if owner.account_kind == "guest":
                    if (ticket is None or not settings.guest_semantic_enabled
                            or not guest_paid_available(settings, "embed")):
                        raise EmbeddingError("embedding_unconfigured")
                    claim, reservation = ticket
                    link = await db.get(GuestOperationLink, (user_id, "embed", claim.operation_key_hash))
                    if (link is None or link.lease_token != claim.lease_token or link.state != "claimed"
                            or link.lease_until <= await database_time(db)
                            or link.reservation_id != reservation.id):
                        raise EmbeddingError("embedding_unconfigured")
                    await mark_guest_dispatched(db, reservation.id)
                # Checks follow marker/heartbeat/admission waits. The document payload
                # comes from this current resource, never the earlier detached copy.
                document_cutoff = None
                if document_job is not None:
                    value, document_cutoff = await _document_dispatch(db, settings, user_id, document_job)
                bound = await guest_deadline(db, owner)
            dispatched = ticket is not None
            timeout = settings.voyage_timeout_seconds
            if bound is not None:
                timeout = min(timeout, max(0, bound.remaining()))
            if document_cutoff is not None:
                timeout = min(timeout, max(0, document_cutoff - time.monotonic()))
            async with asyncio.timeout(timeout):
                if bound is not None and bound.remaining() <= 0:
                    raise guest_expired()
                if document_cutoff is not None and document_cutoff <= time.monotonic():
                    raise EmbeddingError("embedding_unconfigured")
                result = await provider.embed(value, input_type)
            known = True
            if bound is not None and bound.remaining() <= 0:
                raise guest_expired()
            return validate_vector(result, settings.voyage_dimensions)
    finally:
        if ticket is not None:
            await asyncio.shield(_settle_guest_embed(database, user_id, ticket, known=known, dispatched=dispatched))


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
                        ai.policy_version == "v1",
                        mem.policy_version == "v1",
                        Memory.status == "active",
                        Memory.bot_id.in_(MEMORY_BOTS),
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
            ticket = None
            owner = await db.get(User, user_id)
            if owner is not None and owner.account_kind == "guest":
                ticket = await _guest_embed_admission(db, owner, job, settings)
                if ticket is None:
                    # Unavailable price/budget, exhausted quota or an earlier attempt: no send, no retry.
                    job.status, job.lease_token, job.lease_until = "cancelled", None, None
                    continue
        error: str | None = None
        vector: list[float] = []
        try:
            expected = {k: getattr(job, k) for k in ("preference_version", "ai_consent_version", "mem_consent_version")}
            vector = await _guest_embedding_call(database, settings, provider, user_id, ticket, text,
                "document", expected, document_job=(job_id, token))
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
    operation_key: str | None = None,
) -> list[str]:
    if bot_id not in MEMORY_BOTS:
        return []
    ticket = None
    async with database.require()() as db, db.begin():
        user = await lock_actor(db, actor)
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
        if user.account_kind == "guest":
            ticket = await _guest_embedding_ticket(db, user, settings, key=operation_key or f"embed-query:{uuid4()}",
                payload=hashlib.sha256(f"{bot_id}:{data_version}:{query}".encode()).hexdigest(), document=False)
            if ticket is None:
                return await _fallback(db, actor.user_id, bot_id, query, settings)
    try:
        if ticket is not None:
            vector = await _guest_embedding_call(database, settings, provider or VoyageProvider(settings), actor.user_id, ticket,
                query[:8000], "query", _snapshot(auth))
        else:
            vector = validate_vector(await (provider or VoyageProvider(settings)).embed(query[:8000], "query"), settings.voyage_dimensions)
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
