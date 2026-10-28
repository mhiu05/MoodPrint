"""Durable guest cleanup and provider-orphan reconciliation, isolated from other workers.

Both loops always run: no feature flag disables expiry, cleanup, reconciliation or settlement.
A failure never reactivates a guest (authorization is the database predicate, not this worker),
and no attempt that reached ``signup_started`` is ever sent upstream again. Error codes are an
allowlist; no SQL text, provider payload, user id or token is logged.
"""

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.database.models import User
from app.modules.guests.accounting import settle_stale_reservations
from app.modules.guests.lifecycle import purge_guest
from app.modules.guests.models import (
    GuestAbuseBucket,
    GuestBudgetDay,
    GuestCleanupJob,
    GuestCostReservation,
    GuestOperationLink,
    GuestProvisioningAttempt,
)
from app.modules.guests.policy import database_time

log = logging.getLogger("moodprint")

BATCH = 10
LEASE_SECONDS = 30
# 5s, 15s, 60s, 300s, 900s, then hourly with an alert (never abandoned, never reactivated).
BACKOFF = (5, 15, 60, 300, 900)
HOURLY = 3600
ALERT_AFTER_ATTEMPTS = len(BACKOFF)
# Zero-match marker lookups: 5s, 30s, 5min, then hourly until reconcile_until (24h), then incident.
ORPHAN_POLLS = (5, 30, 300)
ERROR_CODES = {"purge_failed", "helper_denied", "database_unavailable"}


def retry_delay(attempts: int) -> int:
    return BACKOFF[attempts - 1] if 0 < attempts <= len(BACKOFF) else HOURLY


def error_code(error: Exception) -> str:
    sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
    if sqlstate in ("42501",):
        return "helper_denied"
    if sqlstate and sqlstate.startswith("08"):
        return "database_unavailable"
    return "purge_failed"


async def ensure_cleanup_jobs(app: FastAPI) -> int:
    """Insert the missing job for any guest row; never changes kind, deadline or access."""
    async with app.state.database.require()() as db, db.begin():
        rows = (
            await db.execute(
                insert(GuestCleanupJob)
                .from_select(
                    ["user_id", "due_at"],
                    select(User.id, User.guest_expires_at).where(
                        User.account_kind == "guest",
                        User.guest_expires_at.is_not(None),
                        ~select(GuestCleanupJob.user_id)
                        .where(GuestCleanupJob.user_id == User.id)
                        .exists(),
                    ),
                )
                .on_conflict_do_nothing()
                .returning(GuestCleanupJob.user_id)
            )
        ).all()
    return len(rows)


async def _claim_cleanup(app: FastAPI) -> tuple[UUID, UUID] | None:
    """Lease one due job (job row only; the owner is locked later, in the purge transaction)."""
    async with app.state.database.require()() as db, db.begin():
        now = await database_time(db)
        job = await db.scalar(
            select(GuestCleanupJob)
            .where(
                GuestCleanupJob.due_at <= now,
                or_(
                    and_(
                        GuestCleanupJob.state.in_(("pending", "retry")),
                        GuestCleanupJob.next_attempt_at <= now,
                    ),
                    and_(GuestCleanupJob.state == "running", GuestCleanupJob.lease_until <= now),
                ),
            )
            .order_by(GuestCleanupJob.due_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        token = uuid4()
        job.state, job.lease_token = "running", token
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        job.attempts += 1
        return job.user_id, token


async def _schedule_retry(app: FastAPI, user_id: UUID, token: UUID, error: Exception) -> None:
    async with app.state.database.require()() as db, db.begin():
        now = await database_time(db)
        job = await db.get(GuestCleanupJob, user_id, with_for_update=True)
        if job is None or job.lease_token != token:
            return  # the lease moved on; the new holder owns the outcome
        job.state = "retry"
        job.lease_token, job.lease_until = None, None
        job.last_error = error_code(error)
        job.next_attempt_at = now + timedelta(seconds=retry_delay(job.attempts))
        if job.attempts >= ALERT_AFTER_ATTEMPTS and job.alerted_at is None:
            job.alerted_at = now
            log.error("metric=guest_cleanup_alert attempts=%d code=%s", job.attempts, job.last_error)


async def process_guest_cleanup(app: FastAPI) -> int:
    """One bounded tick: lease, purge in its own transaction, retry durably, never reactivate."""
    done = 0
    for _ in range(BATCH):
        claimed = await _claim_cleanup(app)
        if claimed is None:
            break
        user_id, token = claimed
        try:
            async with app.state.database.require()() as db, db.begin():
                result = await purge_guest(db, user_id, token)
        except Exception as error:  # rolled back as a whole; retried from the durable job
            await _schedule_retry(app, user_id, token, error)
            log.warning("metric=guest_cleanup_retry code=%s", error_code(error))
            continue
        if result == "removed":
            # Best-effort acceleration after commit: authorization already failed at T.
            app.state.ai.expire_guest(user_id)
            app.state.exports = {
                key: value
                for key, value in app.state.exports.items()
                if value["owner"] != user_id
            }
        done += result == "removed"
    return done


async def reconcile_guest_provisioning(app: FastAPI) -> int:
    """Resolve attempts whose provider outcome is unknown, via the stored marker only.

    Never sends a signup. A lease-expired ``signup_started`` becomes ``ambiguous`` (its grant
    fence is gone); a single verified match is deleted once; zero matches are polled on a
    schedule until the 24h window ends, then escalate to ``incident_required``; multiple or
    unexpected matches are incidents. Stale intents and old terminal attempts are removed.
    """
    handled = 0
    sessions = app.state.database.require()
    async with sessions() as db, db.begin():
        now = await database_time(db)
        await db.execute(
            update(GuestProvisioningAttempt)
            .where(
                GuestProvisioningAttempt.state == "signup_started",
                GuestProvisioningAttempt.lease_until <= now,
            )
            .values(state="ambiguous", lease_token=None, lease_until=None, next_attempt_at=now)
        )
        await db.execute(
            delete(GuestProvisioningAttempt).where(
                or_(
                    and_(
                        GuestProvisioningAttempt.state == "intent",
                        GuestProvisioningAttempt.intent_expires_at < now - timedelta(hours=1),
                    ),
                    and_(
                        GuestProvisioningAttempt.state.in_(("resolved", "rejected")),
                        GuestProvisioningAttempt.next_attempt_at < now - timedelta(hours=24),
                    ),
                )
            )
        )
        ids = (
            await db.scalars(
                select(GuestProvisioningAttempt.id)
                .where(
                    GuestProvisioningAttempt.state.in_(("ambiguous", "orphan_pending")),
                    GuestProvisioningAttempt.next_attempt_at <= now,
                )
                .order_by(GuestProvisioningAttempt.next_attempt_at)
                .limit(BATCH)
            )
        ).all()
    for attempt_id in ids:
        async with sessions() as db, db.begin():
            now = await database_time(db)
            attempt = await db.get(GuestProvisioningAttempt, attempt_id, with_for_update=True)
            if attempt is None or attempt.state not in ("ambiguous", "orphan_pending"):
                continue
            outcome = await db.scalar(
                text("select moodprint.delete_orphan_guest_identity(:attempt)"),
                {"attempt": attempt_id},
            )
            attempt.attempts += 1
            if outcome == "deleted":
                attempt.state, attempt.last_error = "resolved", None
                attempt.next_attempt_at = now
            elif outcome == "incident_required":
                attempt.state, attempt.last_error = "incident_required", "orphan_incident"
                log.error("metric=guest_orphan_incident reason=unexpected_match")
            elif now >= attempt.reconcile_until:
                attempt.state, attempt.last_error = "incident_required", "orphan_unresolved"
                log.error("metric=guest_orphan_incident reason=window_elapsed")
            else:
                # attempts counts the signup itself, so the first lookup is poll number 0.
                poll = attempt.attempts - 2
                step = ORPHAN_POLLS[poll] if 0 <= poll < len(ORPHAN_POLLS) else HOURLY
                attempt.next_attempt_at = now + timedelta(seconds=step)
            handled += 1
    return handled


async def guest_metrics(app: FastAPI) -> dict[str, float]:
    """Content-free counts only: no user id, token, address or content."""
    async with app.state.database.require()() as db:
        now = await database_time(db)
        lag = await db.scalar(
            select(func.max(func.extract("epoch", now - GuestCleanupJob.due_at))).where(
                GuestCleanupJob.due_at <= now
            )
        )
        retries = await db.scalar(
            select(func.count()).select_from(GuestCleanupJob).where(GuestCleanupJob.state == "retry")
        )
        incidents = await db.scalar(
            select(func.count())
            .select_from(GuestCleanupJob)
            .where(GuestCleanupJob.state == "incident_required")
        )
        orphans = await db.scalar(
            select(func.count())
            .select_from(GuestProvisioningAttempt)
            .where(GuestProvisioningAttempt.state.in_(("ambiguous", "orphan_pending")))
        )
    return {
        "guest_cleanup_lag_seconds": float(lag or 0),
        "guest_cleanup_retry_count": float(retries or 0),
        "guest_orphan_count": float(orphans or 0),
        "guest_incident_count": float(incidents or 0),
    }


async def settle_stale_liability(app: FastAPI) -> int:
    """Charge a stale reservation (lost worker/restart) uncertain or release it; never replay it."""
    async with app.state.database.require()() as db, db.begin():
        return await settle_stale_reservations(db)


async def retention_tick(app: FastAPI) -> dict[str, int]:
    """Expire security counters and resolved accounting records; never delete live liability.

    Network buckets live at most 24 h; random terminal reservation records 24 h after they are
    final; unlinked daily totals 30 days (proposed, owner decision D01) and only when no
    reservation still references the day. No identifier is retained in any of them.
    """
    async with app.state.database.require()() as db, db.begin():
        now = await database_time(db)
        buckets = await db.execute(
            delete(GuestAbuseBucket).where(GuestAbuseBucket.expires_at < now).returning(GuestAbuseBucket.scope)
        )
        reservations = await db.execute(
            delete(GuestCostReservation)
            .where(
                GuestCostReservation.state.in_(("settled", "uncertain", "cancelled")),
                GuestCostReservation.lease_until < now - timedelta(hours=24),
                ~select(GuestOperationLink.reservation_id)
                .where(GuestOperationLink.reservation_id == GuestCostReservation.id)
                .exists(),
            )
            .returning(GuestCostReservation.id)
        )
        days = await db.execute(
            delete(GuestBudgetDay)
            .where(
                GuestBudgetDay.day < (now - timedelta(days=30)).date(),
                GuestBudgetDay.halted_at.is_(None),
                ~select(GuestCostReservation.id)
                .where(GuestCostReservation.day == GuestBudgetDay.day)
                .exists(),
            )
            .returning(GuestBudgetDay.day)
        )
    return {
        "buckets": len(buckets.all()),
        "reservations": len(reservations.all()),
        "days": len(days.all()),
    }
