"""Guest policy predicates that do not touch the database."""

from app.core.config import Settings


def guest_paid_available(settings: Settings) -> bool:
    """Paid guest AI/STT/embed is open only with an approved positive budget and known prices.

    Unset, zero or unknown values fail closed: they never mean unlimited, and synthetic fixture
    prices are never inferred for production.
    """
    budget = settings.guest_daily_budget_usd
    return bool(settings.guest_paid_enabled and budget and budget > 0 and settings.guest_pricing_json)
