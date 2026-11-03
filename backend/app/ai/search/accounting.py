from datetime import UTC, timedelta
from decimal import Decimal

from sqlalchemy import case, func, or_, select, text

from app.ai.accounting import RUN_RESERVATION_NANO, budget_liability, liability_scope
from app.ai.persistence import quota_day_start
from app.ai.search.models import AiSearchUsage
from app.ai.search.policy import search_ready
from app.core.errors import DomainError
from app.infrastructure.database.models import AiUsage

WEB_FEE_NANO = 10_000_000
MAPS_CAP_NANO = 500_000_000


def relevant(at):
    since = at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return or_(AiSearchUsage.created_at >= since, AiSearchUsage.state != "settled", AiSearchUsage.tokens_uncertain.is_(True))


async def external_liability(db, at, *, subset=False) -> int:
    fee = case((AiSearchUsage.state == "settled", AiSearchUsage.actual_nano_usd),
               else_=AiSearchUsage.reservation_nano_usd)
    # Global already includes attached AiUsage in its own window; the subset counts those same
    # tokens once (never ones the global window has released), detached ones via the fallback.
    detached = (AiUsage.run_id.is_(None), AiSearchUsage.token_liability_nano_usd)
    tokens = case(detached, (liability_scope(at), func.coalesce(AiUsage.estimated_nano_usd,
                  AiSearchUsage.token_liability_nano_usd)), else_=0) if subset else case(detached, else_=0)
    return int(await db.scalar(select(func.coalesce(func.sum(fee + tokens), 0)).select_from(AiSearchUsage)
        .outerjoin(AiUsage, AiUsage.run_id == AiSearchUsage.child_run_id).where(relevant(at))) or 0)


async def claim(db, settings, user, run_id, provider):
    if not search_ready(settings, provider):
        raise DomainError(503, "SEARCH_UNAVAILABLE", "Công cụ tìm kiếm chưa sẵn sàng.")
    await db.execute(text("select pg_advisory_xact_lock(664201, 1)"))
    previous = await db.scalar(select(AiSearchUsage).where(AiSearchUsage.parent_run_id == run_id,
                                                        AiSearchUsage.provider == provider))
    if previous:
        raise DomainError(409, "SEARCH_ALREADY_DISPATCHED", "Lượt tìm kiếm này đã được tiếp nhận.")
    at = await db.scalar(select(func.clock_timestamp()))
    daily = int(await db.scalar(select(func.count()).select_from(AiSearchUsage).where(
        AiSearchUsage.user_id == user.id, AiSearchUsage.created_at >= quota_day_start(at))) or 0)
    own = int(await db.scalar(select(func.count()).select_from(AiSearchUsage).where(
        AiSearchUsage.user_id == user.id, AiSearchUsage.active.is_(True))) or 0)
    active = int(await db.scalar(select(func.count()).select_from(AiSearchUsage).where(AiSearchUsage.active.is_(True))) or 0)
    if daily >= settings.ai_search_daily_cap_per_user or own >= settings.ai_search_user_concurrency or active >= settings.ai_search_global_concurrency:
        raise DomainError(429, "SEARCH_QUOTA", "Đã đạt giới hạn tìm kiếm. Hãy thử lại sau.")
    fee = WEB_FEE_NANO if provider == "openai_web" else MAPS_CAP_NANO
    tokens = RUN_RESERVATION_NANO if provider == "openai_web" else 0
    ceiling = int(Decimal(str(settings.ai_daily_budget_usd)) * 1_000_000_000)
    subset = int(Decimal(str(settings.ai_search_daily_budget_usd)) * 1_000_000_000)
    if (await budget_liability(db, at) + fee + tokens > ceiling
            or await external_liability(db, at, subset=True) + fee + tokens > subset):
        raise DomainError(503, "SEARCH_BUDGET", "Tìm kiếm đã đạt giới hạn chi phí.")
    row = AiSearchUsage(user_id=user.id, parent_run_id=run_id, provider=provider,
        reservation_nano_usd=fee, token_liability_nano_usd=tokens,
        tokens_uncertain=provider == "openai_web",
        pricing_version=settings.ai_web_search_pricing_version if provider == "openai_web" else settings.apify_maps_pricing_version)
    db.add(row)
    await db.flush()
    return row


async def recover_searches(db):
    """Restart never replays a paid search. Expired web attempts retain unknown liability."""
    from app.infrastructure.database.models import now
    rows = (await db.scalars(select(AiSearchUsage).where(AiSearchUsage.provider == "openai_web",
        AiSearchUsage.active.is_(True), AiSearchUsage.updated_at < now()-timedelta(seconds=45))
        .limit(100).with_for_update(skip_locked=True))).all()
    for row in rows:
        usage = await db.get(AiUsage, row.child_run_id) if row.child_run_id else None
        if row.state == "reserved" and usage is not None and usage.requests_started == 0:
            row.state, row.actual_nano_usd = "settled", 0
            row.tokens_uncertain, row.token_liability_nano_usd = False, 0
        else:
            row.state = "uncertain"
            if usage:
                row.token_liability_nano_usd = usage.estimated_nano_usd
                row.tokens_uncertain = usage.state != "settled"
        row.active = False
        row.updated_at = now()
