"""Content-free daily usage receipts survive entry/job deletion.

The caller holds the owner lock. Counts include in-flight reservations and known
successes; unknown process loss stays consumed. No provider work occurs here.
"""

import hashlib
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select

from app.infrastructure.database.models import Idempotency, now
from app.modules.journal.ai_models import JournalAiJob

OPERATION = "journal:embed-usage"
OPERATIONS = {"embed": OPERATION, "memories": "journal:memory-usage"}


def expired_receipts(at):
    # One calendar date can span 50 UTC hours across user timezone changes.
    return or_(and_(Idempotency.operation.not_in(tuple(OPERATIONS.values())), Idempotency.created_at <= at-timedelta(hours=24)),
               and_(Idempotency.operation.in_(tuple(OPERATIONS.values())), Idempotency.created_at <= at-timedelta(hours=72)))


async def _bucket(db, user, day, zone, kind):
    key = day.isoformat()
    row = await db.scalar(select(Idempotency).where(Idempotency.user_id == user.id,
                                                  Idempotency.operation == OPERATIONS[kind], Idempotency.key == key))
    if row is None:
        start = datetime.combine(day, time.min, zone)
        # Conservatively initialize from pre-receipt successful jobs, if any.
        legacy = await db.scalar(select(func.count()).select_from(JournalAiJob).where(
            JournalAiJob.user_id == user.id, JournalAiJob.kind == kind, JournalAiJob.status == "succeeded",
            JournalAiJob.available_at >= start, JournalAiJob.available_at < start+timedelta(days=1)))
        row = Idempotency(user_id=user.id, operation=OPERATIONS[kind], key=key,
                          digest=hashlib.sha256(key.encode()).hexdigest(), receipt={"count": legacy or 0})
        db.add(row)
    return row


async def reserve_daily_capacity(db, user, settings, lease_until, *, kind="embed") -> tuple[str, ...] | None:
    zone = ZoneInfo(user.timezone)
    first, last = now().astimezone(zone).date(), lease_until.astimezone(zone).date()
    days = [first+timedelta(days=index) for index in range((last-first).days+1)]
    buckets = [await _bucket(db, user, day, zone, kind) for day in days]
    cap = settings.journal_embedding_daily_cap_per_user if kind == "embed" else settings.journal_auto_memory_daily_cap_per_user
    if not buckets or any(row.receipt["count"] >= cap for row in buckets):
        return None
    for row in buckets:
        row.receipt = {"count": row.receipt["count"]+1}
    return tuple(day.isoformat() for day in days)


async def settle_daily_capacity(db, user_id, keys, successful_day: str | None, *, kind="embed") -> None:
    for key in keys:
        if key == successful_day:
            continue
        row = await db.scalar(select(Idempotency).where(Idempotency.user_id == user_id,
                                                      Idempotency.operation == OPERATIONS[kind], Idempotency.key == key))
        # Account cleanup may have removed the receipt. Never recreate it here.
        if row:
            row.receipt = {"count": max(0, row.receipt["count"]-1)}
