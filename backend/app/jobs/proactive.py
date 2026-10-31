"""Dedicated check-in worker (phase-1/03, 96 HD-01): ``python -m app.jobs.proactive``.

Runs only in the Compose service ``proactive``; the API process never schedules or generates
check-ins. Coordination lives entirely in PostgreSQL: schedules materialize into jobs with a
unique (user, companion, slot, local day) key, workers claim with ``SKIP LOCKED`` and a lease,
and every state change is fenced by the lease token so a stale worker can never overwrite a
newer attempt. No transaction is ever held across a model call (the executor opens short
transactions around it), and every worker transaction carries lock/statement/idle timeouts.
"""

import argparse
import asyncio
import logging
import signal
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from app.ai.proactive.models import AiProactiveJob, AiProactiveSchedule, AiProactiveSettings
from app.ai.proactive.schedule import local_date, next_occurrence

log = logging.getLogger("moodprint")
LEASE_SECONDS = 90
DEFER_SECONDS = 300
MATERIALIZE_BATCH = 100
MAX_BACKOFF_SECONDS = 900
UNSTARTED = ("pending", "retry")
HEARTBEAT = Path(tempfile.gettempdir()) / "moodprint-proactive.heartbeat"
HEALTH_MAX_AGE = 120
_clock = {"queue_metric": 0.0}

__all__ = ["local_date"]


@dataclass(frozen=True)
class Claimed:
    """A leased job: the token fences every later write by this attempt."""

    id: UUID
    user_id: UUID
    schedule_id: UUID | None
    bot_id: str
    slot: str
    local_date: date
    due_at: datetime
    expires_at: datetime
    attempts: int
    lease_token: UUID
    lease_until: datetime
    schedule_version: int
    settings_version: int


Executor = Callable[[Any, Claimed], Awaitable[None]]


@asynccontextmanager
async def transaction(database):
    """Short worker transaction with HD-03 safety nets (hosted has no idle timeout)."""
    async with database.require()() as db, db.begin():
        await db.execute(
            text(
                "select set_config('lock_timeout', '2s', true),"
                " set_config('statement_timeout', '5s', true),"
                " set_config('idle_in_transaction_session_timeout', '15s', true)"
            )
        )
        yield db


def _metric_state(job_id: UUID, bot_id: str, slot: str, state: str, reason: str | None, attempt: int):
    log.info(
        "proactive_job_state job_id=%s state=%s reason=%s bot=%s slot=%s attempt=%s",
        job_id, state, reason or "-", bot_id, slot, attempt,
    )
    # Alarm counters (deploy/aws/cloudwatch-alarms.json); content-free.
    if state == "failed":
        log.warning("metric=proactive_job_failed reason=%s", reason or "-")
    elif state == "skipped" and reason in ("expired", "missed_window"):
        log.warning("metric=proactive_job_expired reason=%s", reason)


async def materialize_due(db, settings, at: datetime) -> int:
    """Turn due schedules into jobs (at most one per occurrence) and advance next_due_at."""
    rows = (
        await db.scalars(
            select(AiProactiveSchedule)
            .where(
                AiProactiveSchedule.enabled,
                AiProactiveSchedule.next_due_at.is_not(None),
                AiProactiveSchedule.next_due_at <= at,
            )
            .order_by(AiProactiveSchedule.next_due_at)
            .limit(MATERIALIZE_BATCH)
            .with_for_update(skip_locked=True)
        )
    ).all()
    created = 0
    for row in rows:
        prefs = await db.get(AiProactiveSettings, row.user_id)
        if prefs is None:
            row.next_due_at = None
            continue
        occurrence = row.next_due_at
        if row.auto_paused_at is None:
            expires = occurrence + timedelta(minutes=settings.proactive_grace_minutes)
            missed = expires <= at
            values = {
                "user_id": row.user_id, "schedule_id": row.id, "bot_id": row.bot_id,
                "slot": row.slot, "local_date": local_date(occurrence, prefs.timezone),
                "due_at": occurrence, "expires_at": expires,
                "status": "skipped" if missed else "pending",
                "skip_reason": "missed_window" if missed else None,
                "available_at": occurrence, "attempts": 0,
                "schedule_version": row.version, "settings_version": prefs.version,
                "finished_at": at if missed else None,
            }
            # A same-day job cancelled by an edit comes back when the new time is due.
            statement = insert(AiProactiveJob).values(id=uuid4(), **values).on_conflict_do_update(
                index_elements=["user_id", "bot_id", "slot", "local_date"],
                set_={**values, "lease_token": None, "lease_until": None, "worker_id": None,
                      "last_error": None, "conversation_id": None},
                where=and_(AiProactiveJob.status == "cancelled", AiProactiveJob.run_id.is_(None)),
            ).returning(AiProactiveJob.id, AiProactiveJob.status)
            inserted = (await db.execute(statement)).first()
            if inserted:
                created += 1
                _metric_state(inserted[0], row.bot_id, row.slot, inserted[1],
                              values["skip_reason"], 0)
        # Always jump to the next future occurrence: a long outage never builds a backlog.
        row.next_due_at = next_occurrence(
            local_time=row.local_time, weekdays=row.weekdays, paused_until=row.paused_until,
            timezone=prefs.timezone, after=max(at, occurrence),
        )
    return created


async def expire_stale(db, at: datetime) -> int:
    result = await db.execute(
        update(AiProactiveJob)
        .where(AiProactiveJob.status.in_(UNSTARTED), AiProactiveJob.expires_at <= at)
        .values(status="skipped", skip_reason="expired", finished_at=at, lease_token=None,
                lease_until=None)
        .returning(AiProactiveJob.id)
    )
    return len(result.all())


async def claim_job(db, settings, worker_id: UUID, at: datetime) -> Claimed | None:
    """Lease the oldest runnable job; never two live leases for one account."""
    other = aliased(AiProactiveJob)
    for _ in range(5):
        job = await db.scalar(
            select(AiProactiveJob)
            .where(
                or_(
                    and_(
                        AiProactiveJob.status.in_(UNSTARTED),
                        AiProactiveJob.available_at <= at,
                        AiProactiveJob.expires_at > at,
                    ),
                    and_(AiProactiveJob.status == "running", AiProactiveJob.lease_until <= at),
                ),
                ~exists().where(
                    other.user_id == AiProactiveJob.user_id,
                    other.status == "running",
                    other.lease_until > at,
                    other.id != AiProactiveJob.id,
                ),
            )
            .order_by(AiProactiveJob.available_at, AiProactiveJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        if job.expires_at <= at:
            job.status, job.skip_reason, job.finished_at = "skipped", "expired", at
            job.lease_token = job.lease_until = None
            _metric_state(job.id, job.bot_id, job.slot, "skipped", "expired", job.attempts)
            continue
        if job.attempts >= settings.proactive_max_attempts:
            job.status, job.last_error, job.finished_at = "failed", "attempts_exhausted", at
            job.lease_token = job.lease_until = None
            _metric_state(job.id, job.bot_id, job.slot, "failed", "attempts_exhausted", job.attempts)
            continue
        job.status, job.lease_token, job.worker_id = "running", uuid4(), worker_id
        job.lease_until = at + timedelta(seconds=LEASE_SECONDS)
        job.attempts += 1
        await db.flush()
        _metric_state(job.id, job.bot_id, job.slot, "running", None, job.attempts)
        return Claimed(
            job.id, job.user_id, job.schedule_id, job.bot_id, job.slot, job.local_date,
            job.due_at, job.expires_at, job.attempts, job.lease_token, job.lease_until,
            job.schedule_version, job.settings_version,
        )
    return None


def _fenced(claimed: Claimed):
    return update(AiProactiveJob).where(
        AiProactiveJob.id == claimed.id,
        AiProactiveJob.status == "running",
        AiProactiveJob.lease_token == claimed.lease_token,
    )


async def finish(
    db,
    claimed: Claimed,
    status: str,
    *,
    reason: str | None = None,
    error: str | None = None,
    run_id: UUID | None = None,
    conversation_id: UUID | None = None,
    challenge_kind: str | None = None,
) -> bool:
    """Terminal state for this attempt; False when a newer lease owns the job."""
    values: dict[str, Any] = {
        "status": status, "skip_reason": reason if status == "skipped" else None,
        "last_error": error, "finished_at": func.now(), "lease_token": None, "lease_until": None,
    }
    if run_id is not None:
        values["run_id"] = run_id
    if conversation_id is not None:
        values["conversation_id"] = conversation_id
    if challenge_kind is not None:
        values["challenge_kind"] = challenge_kind
    done = (await db.execute(_fenced(claimed).values(**values).returning(AiProactiveJob.id))).first()
    if done:
        _metric_state(claimed.id, claimed.bot_id, claimed.slot, status, reason or error,
                      claimed.attempts)
    return done is not None


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(MAX_BACKOFF_SECONDS, 60 * 2 ** max(0, attempts - 1)))


async def retry(db, claimed: Claimed, *, error: str, at: datetime) -> bool:
    available = at + backoff(claimed.attempts)
    if available >= claimed.expires_at:
        return await finish(db, claimed, "skipped", reason="expired", error=error)
    done = (
        await db.execute(
            _fenced(claimed)
            .values(status="retry", available_at=available, last_error=error,
                    lease_token=None, lease_until=None)
            .returning(AiProactiveJob.id)
        )
    ).first()
    if done:
        _metric_state(claimed.id, claimed.bot_id, claimed.slot, "retry", error, claimed.attempts)
    return done is not None


async def defer(db, claimed: Claimed, *, reason: str, at: datetime) -> bool:
    """Try again in five minutes without spending an attempt (deferring is not failing)."""
    available = at + timedelta(seconds=DEFER_SECONDS)
    if available >= claimed.expires_at:
        return await finish(db, claimed, "skipped", reason=reason)
    done = (
        await db.execute(
            _fenced(claimed)
            .values(status="retry", available_at=available, last_error=reason,
                    attempts=AiProactiveJob.attempts - 1, lease_token=None, lease_until=None)
            .returning(AiProactiveJob.id)
        )
    ).first()
    if done:
        _metric_state(claimed.id, claimed.bot_id, claimed.slot, "retry", reason, claimed.attempts - 1)
    return done is not None


async def _guarded(execute: Executor, runtime, claimed: Claimed) -> None:
    try:
        await execute(runtime, claimed)
    except Exception as error:
        # The executor settles its own run; anything escaping it is retried by lease rules.
        log.error("proactive_executor_error job_id=%s error_type=%s", claimed.id, type(error).__name__)
        with suppress(Exception):
            from app.infrastructure.database.models import now

            async with transaction(runtime.database) as db:
                await retry(db, claimed, error="executor_error", at=now())


async def proactive_tick(runtime, *, execute: Executor | None = None) -> dict:
    """One bounded pass: recover, materialize, expire, then claim ≤ concurrency jobs."""
    from app.ai.accounting import recover_expired
    from app.ai.persistence import recover_turns
    from app.infrastructure.database.models import now

    settings = runtime.settings
    if not settings.proactive_worker_enabled:
        return {"enabled": False}
    if execute is None:
        from app.ai.proactive.executor import execute_job

        execute = execute_job
    started = time.monotonic()
    async with transaction(runtime.database) as db:
        # Runs of a crashed attempt become interrupted before its job is leased again.
        await recover_turns(db)
        if settings.ai_accounting_enabled:
            await recover_expired(db)
        at = now()
        materialized = await materialize_due(db, settings, at)
        expired = await expire_stale(db, at)
        if time.monotonic() >= _clock["queue_metric"]:
            due = await db.scalar(
                select(func.count()).select_from(AiProactiveJob).where(
                    AiProactiveJob.status.in_(UNSTARTED), AiProactiveJob.available_at <= at
                )
            )
            log.info("metric=proactive_queue_due value=%d", due or 0)
            _clock["queue_metric"] = time.monotonic() + 60
    claimed: list[Claimed] = []
    for _ in range(settings.proactive_worker_concurrency):
        async with transaction(runtime.database) as db:
            job = await claim_job(db, settings, runtime.worker_id, now())
        if job is None:
            break
        claimed.append(job)
    run = execute
    await asyncio.gather(*(_guarded(run, runtime, job) for job in claimed))
    log.info("metric=proactive_tick_ms value=%d claimed=%d", round((time.monotonic() - started) * 1000),
             len(claimed))
    return {"enabled": True, "materialized": materialized, "expired": expired, "claimed": len(claimed)}


def beat(path: Path = HEARTBEAT) -> None:
    path.write_text(str(time.time()), encoding="ascii")


def healthy(path: Path = HEARTBEAT, max_age: float = HEALTH_MAX_AGE) -> bool:
    try:
        return time.time() - path.stat().st_mtime <= max_age
    except OSError:
        return False


async def wait_ready(database, stop: asyncio.Event) -> bool:
    """Do not touch check-in tables until the schema is a release this image accepts."""
    from app.core.revisions import READY_REVISIONS

    while not stop.is_set():
        try:
            async with database.require()() as db:
                revision = await db.scalar(text("select version_num from moodprint.alembic_version"))
            if revision in READY_REVISIONS:
                return True
            log.warning("proactive_worker_waiting reason=schema_revision")
        except Exception as error:
            log.warning("proactive_worker_waiting reason=%s", type(error).__name__)
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), 30)
    return False


async def serve(settings, *, stop: asyncio.Event, heartbeat: Path = HEARTBEAT,
                interval: float = 5.0) -> None:
    from app.ai.runtime import AiRuntime
    from app.infrastructure.database.connection import Database

    database = Database(settings)
    runtime = AiRuntime(settings, database)
    log.info("proactive_worker_start enabled=%s concurrency=%d", settings.proactive_worker_enabled,
             settings.proactive_worker_concurrency)
    try:
        beat(heartbeat)
        if not await wait_ready(database, stop):
            return
        while not stop.is_set():
            claimed = 0
            try:
                claimed = (await proactive_tick(runtime)).get("claimed", 0)
            except Exception as error:
                log.error("metric=proactive_tick_error error_type=%s", type(error).__name__)
            beat(heartbeat)
            if claimed:
                continue  # drain due work without waiting
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), interval)
    finally:
        # A job interrupted here keeps its lease and is reclaimed after LEASE_SECONDS.
        await runtime.close()
        if database.engine is not None:
            await database.engine.dispose()
        log.info("proactive_worker_stop")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.jobs.proactive")
    parser.add_argument("--health", action="store_true", help="exit 0 when the loop is alive")
    parser.add_argument("--heartbeat", type=Path, default=HEARTBEAT)
    args = parser.parse_args(argv)
    if args.health:
        return 0 if healthy(args.heartbeat) else 1
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    from app.core.config import Settings

    settings = Settings()

    async def run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
        await serve(settings, stop=stop, heartbeat=args.heartbeat)

    # psycopg's async driver needs a selector loop on Windows (local development only).
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run(), loop_factory=factory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
