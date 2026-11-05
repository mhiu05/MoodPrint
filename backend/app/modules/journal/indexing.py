"""Bounded background derivation: owner -> job locks, provider I/O between transactions."""

import asyncio
import hashlib
import logging
from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.ai.voyage import EmbeddingError, VoyageProvider, validate_vector
from app.infrastructure.database.models import AgeDeclaration, Consent, Memory, User, now
from app.modules.auth.age import adult_eligibility_predicate
from app.modules.journal.ai_models import JournalAiJob, JournalAiSettings, JournalEntryEmbedding
from app.modules.journal.ai_settings import journal_ai_allowed
from app.modules.journal.models import JournalEntry
from app.modules.journal.quota import reserve_daily_capacity, settle_daily_capacity
from app.modules.journal.service import active_dates

log = logging.getLogger("moodprint.journal_index")
ACTIVE = ("pending", "running", "retry")


def journal_document(entry, char_limit: int = 7000) -> str:
    header = (f"Ngày {entry.local_date:%d/%m/%Y}. Tâm trạng {entry.mood}/5.\n"
              f"Cảm xúc: {', '.join(str(tag)[:60] for tag in entry.emotions[:12])}\n"
              f"Yếu tố: {', '.join(str(tag)[:60] for tag in entry.factors[:12])}\n\n")
    return header + entry.text[:min(char_limit, max(0, 8000-len(header)))]


async def on_entry_saved(db, user, entry, settings) -> None:
    from app.ai.journal_memory import enqueue_journal_memory

    await enqueue_journal_memory(db, user, entry, settings)
    version = await journal_ai_allowed(db, user, settings, "embed")
    start, end = active_dates(user)
    if version is None or entry.status != "saved" or not start <= entry.local_date <= end:
        return
    await db.execute(insert(JournalAiJob).values(
        entry_id=entry.id, user_id=user.id, kind="embed", entry_version=entry.version,
        settings_version=version, model=settings.voyage_model, dimensions=settings.voyage_dimensions,
        available_at=now()+timedelta(seconds=settings.journal_embedding_debounce_seconds),
    ).on_conflict_do_update(constraint="uq_journal_ai_jobs_snapshot", set_={
        "status": "pending", "attempts": 0, "dimensions": settings.voyage_dimensions,
        "available_at": now()+timedelta(seconds=settings.journal_embedding_debounce_seconds),
        "lease_token": None, "lease_until": None, "last_error": None,
    }, where=or_(JournalAiJob.status == "cancelled", JournalAiJob.dimensions.is_distinct_from(settings.voyage_dimensions))))


async def on_entry_changed(db, user, entry, settings) -> None:
    await db.execute(delete(JournalEntryEmbedding).where(JournalEntryEmbedding.entry_id == entry.id))
    await db.execute(update(JournalAiJob).where(JournalAiJob.entry_id == entry.id, JournalAiJob.status.in_(ACTIVE)).values(
        status="cancelled", lease_token=None, lease_until=None,
    ))
    await db.execute(delete(Memory).where(Memory.source_entry_id == entry.id, Memory.origin == "journal_auto", Memory.version == 1))
    await on_entry_saved(db, user, entry, settings)


async def reconcile_journal_jobs(database, settings) -> int:
    if not settings.journal_semantic_available:
        return 0
    version = func.coalesce(JournalAiSettings.version, 1)
    local_today = func.timezone(User.timezone, func.clock_timestamp()).cast(Date)
    current_job = exists(select(JournalAiJob.id).where(
        JournalAiJob.entry_id == JournalEntry.id, JournalAiJob.kind == "embed",
        JournalAiJob.entry_version == JournalEntry.version, JournalAiJob.settings_version == version,
        JournalAiJob.model == settings.voyage_model, JournalAiJob.dimensions == settings.voyage_dimensions,
        JournalAiJob.status != "cancelled",
    )).correlate(JournalEntry, JournalAiSettings)
    async with database.require()() as db:
        candidates = (await db.execute(select(JournalEntry.id, User.id).join(User, User.id == JournalEntry.user_id)
            .join(AgeDeclaration, AgeDeclaration.user_id == User.id)
            .outerjoin(JournalAiSettings, JournalAiSettings.user_id == User.id)
            .join(Consent, and_(Consent.user_id == User.id, Consent.purpose == "AI", Consent.policy_version == "v1"))
            .where(User.account_kind == "registered", adult_eligibility_predicate(), User.status == "active", User.deletion_pending.is_(False),
                   JournalEntry.status == "saved", JournalEntry.local_date >= local_today-89, JournalEntry.local_date <= local_today,
                   or_(JournalAiSettings.user_id.is_(None), JournalAiSettings.embedding_enabled.is_(True)), ~current_job)
            .order_by(JournalEntry.id).limit(settings.embedding_job_batch_size))).all()
    count = 0
    for entry_id, uid in candidates:
        async with database.require()() as db, db.begin():
            user = await db.scalar(select(User).where(User.id == uid).with_for_update())
            entry = await db.get(JournalEntry, entry_id)
            if user and entry and await journal_ai_allowed(db, user, settings, "embed") is not None:
                await on_entry_saved(db, user, entry, settings)
                count += 1
    return count


async def _current(db, job, user, settings) -> JournalEntry | None:
    if not user or await journal_ai_allowed(db, user, settings, "embed") != job.settings_version:
        return None
    if job.kind != "embed" or job.model != settings.voyage_model or job.dimensions != settings.voyage_dimensions:
        return None
    entry = await db.get(JournalEntry, job.entry_id)
    start, end = active_dates(user)
    if (not entry or entry.user_id != user.id or entry.version != job.entry_version
            or entry.status != "saved" or not start <= entry.local_date <= end):
        return None
    return entry


def _finish(job, state):
    job.status, job.lease_token, job.lease_until = state, None, None


async def process_journal_jobs(database, settings, *, embedder=None, memory_runner=None) -> int:
    count = await _process_journal_embeddings(database, settings, embedder=embedder)
    if memory_runner is not None:
        from app.ai.journal_memory import process_memory_jobs
        count += await process_memory_jobs(database, settings, memory_runner)
    return count


async def _process_journal_embeddings(database, settings, *, embedder=None) -> int:
    if not settings.journal_semantic_available:
        return 0
    await reconcile_journal_jobs(database, settings)
    provider = embedder or VoyageProvider(settings)
    processed = 0
    for _ in range(settings.embedding_job_batch_size):
        async with database.require()() as db, db.begin():
            # Claim job only, commit, then acquire owner -> job in the next transaction.
            job = await db.scalar(select(JournalAiJob).where(JournalAiJob.kind == "embed", or_(
                and_(JournalAiJob.status.in_(("pending", "retry")), JournalAiJob.available_at <= now()),
                and_(JournalAiJob.status == "running", JournalAiJob.lease_until <= now()),
            )).order_by(JournalAiJob.available_at, JournalAiJob.id).limit(1).with_for_update(skip_locked=True))
            if not job:
                break
            if job.model != settings.voyage_model or job.dimensions != settings.voyage_dimensions:
                _finish(job, "cancelled")
                continue
            if job.attempts >= settings.embedding_max_attempts:
                _finish(job, "failed")
                continue
            job.status, job.lease_token = "running", uuid4()
            job.lease_until = now()+timedelta(seconds=settings.embedding_lease_seconds)
            job.attempts += 1
            identity, uid, token = job.id, job.user_id, job.lease_token
        async with database.require()() as db, db.begin():
            user = await db.scalar(select(User).where(User.id == uid).with_for_update())
            job = await db.get(JournalAiJob, identity, with_for_update=True)
            if not job or job.status != "running" or job.lease_token != token:
                continue
            entry = await _current(db, job, user, settings)
            if not entry:
                _finish(job, "cancelled")
                continue
            quota_keys = await reserve_daily_capacity(db, user, settings, job.lease_until)
            if quota_keys is None:
                _finish(job, "retry")
                job.attempts -= 1
                job.available_at = datetime.combine(active_dates(user)[1]+timedelta(days=1), time(0, 5), ZoneInfo(user.timezone))
                continue
            document = journal_document(entry, settings.journal_document_char_limit)
            lease_until = job.lease_until
            quota_zone = ZoneInfo(user.timezone)
        error = None
        undispatched = False
        vector = None
        try:
            async with asyncio.timeout(min(settings.voyage_timeout_seconds, max(0, (lease_until-now()).total_seconds()))):
                vector = validate_vector(await provider.embed(document, "document"), settings.voyage_dimensions)
        except Exception as failure:
            error = "embedding_provider_unavailable"
            undispatched = isinstance(failure, EmbeddingError) and str(failure) in (
                "embedding_unconfigured", "embedding_input_invalid",
            )
        successful_day = now().astimezone(quota_zone).date().isoformat() if vector is not None else None
        async with database.require()() as db, db.begin():
            user = await db.scalar(select(User).where(User.id == uid).with_for_update())
            # Charge valid provider successes even after entry/job deletion.
            # Settle once in the same transaction as fenced publication; a crash
            # before it commits retains reservations conservatively.
            if vector is not None or undispatched:
                await settle_daily_capacity(db, uid, quota_keys, successful_day)
            # Transport loss/timeout or an invalid response may already be billed.
            # Keep their reservations, including the possible next local day.
            job = await db.get(JournalAiJob, identity, with_for_update=True)
            if (not job or job.status != "running" or job.lease_token != token
                    or not job.lease_until or job.lease_until <= now()):
                continue
            entry = await _current(db, job, user, settings)
            if not entry:
                _finish(job, "cancelled")
            elif error:
                _finish(job, "failed" if job.attempts >= settings.embedding_max_attempts else "retry")
                job.last_error = error
                job.available_at = now()+timedelta(seconds=5*2**(job.attempts-1))
            else:
                await db.execute(delete(JournalEntryEmbedding).where(JournalEntryEmbedding.entry_id == job.entry_id))
                db.add(JournalEntryEmbedding(entry_id=job.entry_id, user_id=uid, entry_version=job.entry_version,
                    settings_version=job.settings_version, model=job.model, dimensions=job.dimensions,
                    content_sha256=hashlib.sha256(document.encode()).hexdigest(), embedding=vector))
                _finish(job, "succeeded")
                # Completion-day accounting; queued backfills can span midnight.
                job.available_at = now()
                job.last_error = None
            log.info("journal_index_attempt state=%s attempt=%s error=%s", job.status, job.attempts, job.last_error or "none")
        processed += 1
    if processed:
        async with database.require()() as db:
            counts = dict((await db.execute(select(JournalAiJob.status, func.count()).where(JournalAiJob.kind == "embed").group_by(JournalAiJob.status))).all())
        log.info("journal_index_queue pending=%d retry=%d failed=%d", *(counts.get(state, 0) for state in ("pending", "retry", "failed")))
    return processed
