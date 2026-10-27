"""Configuration-only readiness for the public landing and guest entry (never touches identity)."""

from typing import Literal

from fastapi import Request

from app.modules.guests.schemas import PublicExperience


def experience_view(request: Request) -> PublicExperience:
    """Capability readiness from configuration only; reading it never creates an identity."""
    settings = request.app.state.settings
    database_ready = request.app.state.database.sessions is not None
    configured = all(
        (
            settings.supabase_url,
            settings.supabase_publishable_key.get_secret_value(),
            settings.guest_captcha_site_key,
            settings.guest_abuse_hmac_key.get_secret_value(),
            database_ready,
        )
    )
    reason: Literal["disabled", "configuration_missing", "temporarily_unavailable"] | None
    if not settings.guest_auth_enabled:
        reason = "disabled"
    elif not configured:
        reason = "configuration_missing"
    else:
        reason = None
    available = reason is None
    return PublicExperience(
        guest_available=available,
        guest_unavailable_reason=reason,
        feedback_available=settings.feedback_enabled and database_ready,
        product_tour_available=settings.product_tour_enabled,
        captcha_site_key=settings.guest_captcha_site_key if available else None,
    )
