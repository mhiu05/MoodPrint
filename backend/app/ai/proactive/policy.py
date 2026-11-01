"""Who may receive check-ins from which companion (phase-1/05 §3).

The API uses ``eligibility_reason`` to explain and to refuse enabling a schedule; the worker
re-derives the same answer from live rows before every model call and again at publish.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sqlalchemy import func, select, text

from app.ai.models import AiMessageRecord
from app.ai.persistence import spent_today_nano
from app.ai.proactive.models import (
    AiConversationRead,
    AiProactiveJob,
    AiProactiveSchedule,
    AiProactiveSettings,
)
from app.core.errors import DomainError
from app.core.security import assert_purpose
from app.infrastructure.database.models import AiRun, Consent, User, now
from app.modules.auth.age import is_adult_eligible
from app.modules.consent.policy import consent_enabled

log = logging.getLogger("moodprint")
AUTO_PAUSE_UNOPENED = 3


def available(settings, runtime, user: User) -> bool:
    """Feature flag, rollout cohort and live AI service for a registered account."""
    return (
        user.account_kind == "registered"
        and settings.proactive_open_for(user.id)
        and runtime.available_for(user.id)
    )


async def match_enabled(db, user: User) -> bool:
    consent = await db.scalar(
        select(Consent).where(Consent.user_id == user.id, Consent.purpose == "MATCH")
    )
    return bool(consent and consent_enabled("MATCH", consent.enabled))


def v3_reason(settings, user: User, bot_id: str) -> str | None:
    """V3: a legacy companion's schedule is preserved but never runs while the three agents are
    on; a V3 agent never sends a check-in while they are off (nothing is moved silently)."""
    from app.ai.agents import is_legacy, is_v3

    v3 = settings.v3_open_for(user.id)
    if v3 and is_legacy(bot_id):
        return "legacy_companion"
    if not v3 and is_v3(bot_id):
        return "agent_unavailable"
    return None


def eligibility_reason(*, settings, user: User, bot_id: str, match: bool) -> str | None:
    if not settings.chat_history_enabled:
        # Check-ins are delivered into saved conversations; without history there is nowhere.
        return "history_unavailable"
    if reason := v3_reason(settings, user, bot_id):
        return reason
    if bot_id == "caunoi":
        # Same rule as assert_purpose(MATCH): adult, social consent, no active restriction.
        if user.age_band != "adult":
            return "teen_social_unavailable"
        if not match:
            return "social_not_enabled"
        if user.social_restricted_until and user.social_restricted_until > now():
            return "social_restricted"
    return None


@dataclass(frozen=True)
class Decision:
    """A content-free reason not to run this job now."""

    outcome: Literal["skip", "cancel", "defer", "retry"]
    reason: str


@dataclass
class Authorized:
    user: User
    prefs: AiProactiveSettings
    schedule: AiProactiveSchedule


async def authorize_proactive(
    db, settings, runtime, job: AiProactiveJob, *, lock: bool = True
) -> Authorized | Decision:
    """Live eligibility for a sessionless check-in. No Actor, session or tool is involved.

    Called at E1 (before any model call), from the pre-request hook, and again under the
    owner lock at publish. ``lock`` takes the account row first (users → jobs → conversations).
    """
    statement = select(User).where(User.id == job.user_id)
    user = await db.scalar(statement.with_for_update() if lock else statement)
    if user is None or user.status != "active" or user.account_kind != "registered":
        return Decision("skip", "ineligible_account")
    if user.deletion_pending:
        return Decision("cancel", "deletion_pending")
    at = now()
    if (user.suspended_until and user.suspended_until > at) or not await is_adult_eligible(db, user):
        # Global 18+: the stored declaration decides, not the legacy age_band label.
        return Decision("skip", "ineligible_account")
    if not settings.proactive_open_for(user.id):
        return Decision("skip", "disabled")
    if not runtime.available_for(user.id):
        return Decision("skip", "ai_unavailable")
    if not settings.chat_history_enabled:
        return Decision("skip", "no_history_capability")
    try:
        await assert_purpose(db, user, "AI")
    except DomainError:
        return Decision("skip", "ineligible_account")
    prefs = await db.get(AiProactiveSettings, user.id)
    schedule = await db.get(AiProactiveSchedule, job.schedule_id) if job.schedule_id else None
    if prefs is None or schedule is None or not schedule.enabled or schedule.user_id != user.id:
        return Decision("skip", "disabled")
    # Saving a schedule counts as activity: last_seen_at only moves with the session slide.
    seen = max(value for value in (user.last_seen_at, schedule.updated_at) if value)
    if seen < at - timedelta(days=settings.proactive_inactive_days):
        return Decision("skip", "inactive_user")
    if (schedule.version, prefs.version) != (job.schedule_version, job.settings_version):
        return Decision("cancel", "version_changed")
    if schedule.paused_until and job.local_date <= schedule.paused_until:
        return Decision("skip", "paused")
    if schedule.auto_paused_at:
        return Decision("skip", "auto_paused")
    if reason := v3_reason(settings, user, job.bot_id):
        return Decision("skip", reason)
    if job.bot_id == "caunoi":
        match = await match_enabled(db, user)
        if eligibility_reason(settings=settings, user=user, bot_id="caunoi", match=match):
            return Decision("skip", "ineligible_social")
    return Authorized(user, prefs, schedule)


async def _unopened(db, job: AiProactiveJob) -> bool:
    """The user neither scrolled past the check-in nor replied after it."""
    if job.run_id is None or job.conversation_id is None:
        return False
    first = await db.scalar(
        select(func.min(AiMessageRecord.sequence)).where(AiMessageRecord.run_id == job.run_id)
    )
    if first is None:
        return False  # deleted with its conversation: never count against the companion
    read = await db.scalar(
        select(AiConversationRead.last_read_sequence).where(
            AiConversationRead.conversation_id == job.conversation_id
        )
    )
    replied = await db.scalar(
        select(AiMessageRecord.id).where(
            AiMessageRecord.conversation_id == job.conversation_id,
            AiMessageRecord.actor == "self",
            AiMessageRecord.sequence > first,
        ).limit(1)
    )
    return (read or 0) < first and replied is None


async def admit_proactive(
    db, settings, authorized: Authorized | Decision, job: AiProactiveJob
) -> Decision | None:
    """E1 limits after authorization; None admits the job. Shares chat's admission lock."""
    if isinstance(authorized, Decision):
        return authorized
    user, schedule = authorized.user, authorized.schedule
    # Same advisory lock as admission(): AI_GLOBAL_CONCURRENCY stays one system-wide ceiling.
    await db.execute(text("select pg_advisory_xact_lock(664201, 1)"))
    running = await db.scalar(
        select(func.count()).select_from(AiRun).where(AiRun.status == "running")
    )
    if running >= settings.ai_global_concurrency:
        return Decision("defer", "capacity")
    if settings.ai_accounting_enabled and settings.ai_daily_budget_usd > 0:
        ceiling = settings.ai_daily_budget_usd * 1_000_000_000
        if await spent_today_nano(db, now()) >= settings.proactive_budget_share * ceiling:
            log.warning("metric=proactive_budget_skip")
            return Decision("skip", "budget")
    delivered = await db.scalar(
        select(func.count()).select_from(AiProactiveJob).where(
            AiProactiveJob.user_id == user.id,
            AiProactiveJob.local_date == job.local_date,
            AiProactiveJob.status == "delivered",
        )
    )
    if delivered >= settings.proactive_daily_cap_per_user:
        return Decision("skip", "daily_cap")
    chatting = await db.scalar(
        select(AiRun.id).where(
            AiRun.user_id == user.id, AiRun.bot_id == job.bot_id,
            AiRun.origin == "user", AiRun.status == "running",
        ).limit(1)
    )
    if chatting is not None:
        return Decision("defer", "active_chat")
    recent = (
        await db.scalars(
            select(AiProactiveJob).where(
                AiProactiveJob.user_id == user.id,
                AiProactiveJob.bot_id == job.bot_id,
                AiProactiveJob.status == "delivered",
                AiProactiveJob.id != job.id,
            ).order_by(AiProactiveJob.due_at.desc()).limit(AUTO_PAUSE_UNOPENED)
        )
    ).all()
    if len(recent) == AUTO_PAUSE_UNOPENED and all([await _unopened(db, r) for r in recent]):
        # OD-05: stop after three unopened check-ins in a row; one tap turns it back on.
        schedule.auto_paused_at = now()
        return Decision("skip", "auto_paused")
    return None
