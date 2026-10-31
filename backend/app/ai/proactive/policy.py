"""Who may receive check-ins from which companion (phase-1/05 §3).

The API uses ``eligibility_reason`` to explain and to refuse enabling a schedule; the worker
re-derives the same answer from live rows before every model call and again at publish.
"""

from sqlalchemy import select

from app.infrastructure.database.models import Consent, User, now
from app.modules.consent.policy import consent_enabled


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


def eligibility_reason(*, settings, user: User, bot_id: str, match: bool) -> str | None:
    if not settings.chat_history_enabled:
        # Check-ins are delivered into saved conversations; without history there is nowhere.
        return "history_unavailable"
    if bot_id == "caunoi":
        # Same rule as assert_purpose(MATCH): adult, social consent, no active restriction.
        if user.age_band != "adult":
            return "teen_social_unavailable"
        if not match:
            return "social_not_enabled"
        if user.social_restricted_until and user.social_restricted_until > now():
            return "social_restricted"
    return None
