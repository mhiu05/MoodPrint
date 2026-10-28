"""Feedback availability: one predicate shared by the routes, the session view and readiness."""

from app.core.config import Settings


def feedback_open(settings: Settings) -> bool:
    """Collection needs the rollout flag *and* the HMAC key that keys its abuse counters.

    Without the key a submission could not be rate limited, so the endpoints do not exist rather
    than accept unmetered input.
    """
    return settings.feedback_enabled and bool(settings.guest_abuse_hmac_key.get_secret_value())
