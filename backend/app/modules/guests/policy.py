"""Guest lifetime policy: one clock source, one pure predicate, one explicit registered gate."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import DomainError
from app.infrastructure.database.models import User

GUEST_LIFETIME_SECONDS = 7200


def guest_paid_available(settings: Settings) -> bool:
    """Paid guest AI/STT/embed is open only with an approved positive budget and known prices.

    Unset, zero or unknown values fail closed: they never mean unlimited, and synthetic fixture
    prices are never inferred for production.
    """
    budget = settings.guest_daily_budget_usd
    return bool(settings.guest_paid_enabled and budget and budget > 0 and settings.guest_pricing_json)


def guest_expired() -> DomainError:
    return DomainError(401, "GUEST_EXPIRED", "Lượt dùng thử đã kết thúc.", clear_session=True)


async def database_time(db: AsyncSession) -> datetime:
    """The database clock is the only deadline authority; there is deliberately no override."""
    at = await db.scalar(select(func.clock_timestamp()))
    if at is None:
        raise RuntimeError("Database clock unavailable")
    return at


def lifetime_allows(user: User, at: datetime) -> bool:
    """Pure predicate: registered accounts keep their sliding policy, a guest ends at T exactly."""
    if user.account_kind != "guest":
        return True
    return user.guest_expires_at is not None and at < user.guest_expires_at


async def assert_guest_active(db: AsyncSession, user: User) -> None:
    """Fresh-clock check for a guest; raises 401 GUEST_EXPIRED at or after T. No-op for registered."""
    if user.account_kind == "guest" and not lifetime_allows(user, await database_time(db)):
        raise guest_expired()


def require_registered_user(user: User) -> None:
    if user.account_kind == "guest":
        raise DomainError(
            403,
            "REGISTERED_REQUIRED",
            "Tạo tài khoản để dùng tính năng này. Lượt dùng thử không có tìm bạn và nhắn tin.",
        )
