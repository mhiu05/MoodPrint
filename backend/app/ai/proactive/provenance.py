"""Revalidate a journal-derived check-in before it may join a later chat context (ADR-08)."""

from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.ai.proactive.models import AiMessageSource, AiProactiveSettings
from app.infrastructure.database.models import now

JOURNAL_POLICY = "proactive-journal-v1"
# Older journal check-ins are simply cut from context (fail closed), never re-read.
REVALIDATION_WINDOW = timedelta(hours=36)


def source_policy(prefs: AiProactiveSettings) -> str:
    # ≤ 32 chars. Re-enabling consent bumps the version, so older check-ins never revalidate.
    return f"{JOURNAL_POLICY}@{prefs.journal_context_version}"


async def revalidate_sources(db, user, run_ids) -> frozenset[UUID]:
    """Runs whose every source is still the same saved, owner, in-window revision under live consent.

    The caller holds the owner lock. Deleting/editing an entry or switching journal use off
    (even off and on again) makes the check-in unusable as context.
    """
    from app.modules.journal.models import JournalEntry

    ids = set(run_ids)
    if not ids:
        return frozenset()
    prefs = await db.get(AiProactiveSettings, user.id)
    if prefs is None or not prefs.journal_context_enabled:
        return frozenset()
    rows = (
        await db.scalars(
            select(AiMessageSource).where(
                AiMessageSource.run_id.in_(ids), AiMessageSource.user_id == user.id
            )
        )
    ).all()
    today = now().astimezone(ZoneInfo(user.timezone)).date()
    current = dict(
        (
            await db.execute(
                select(JournalEntry.id, JournalEntry.version).where(
                    JournalEntry.user_id == user.id,
                    JournalEntry.id.in_([row.source_id for row in rows]),
                    JournalEntry.status == "saved",
                    JournalEntry.local_date >= today - timedelta(days=89),
                    JournalEntry.local_date <= today,
                )
            )
        ).all()
    ) if rows else {}
    by_run: dict[UUID, list[AiMessageSource]] = {}
    for row in rows:
        by_run.setdefault(row.run_id, []).append(row)
    policy = source_policy(prefs)
    return frozenset(
        run_id
        for run_id, sources in by_run.items()
        if all(s.policy == policy and current.get(s.source_id) == s.source_revision for s in sources)
    )
