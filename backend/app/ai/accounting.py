"""Idempotent metadata accounting. Unknown provider usage is never refunded or invented."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, text, update

from app.ai.envelope import BOUNDED_PRICING_VERSION, BOUNDED_RESERVATION_NANO
from app.ai.usage import UsageEvent
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, AiUsage, User, now

PRICING_VERSION = "openai-standard-2026-10-24"
# Integer nano-USD/token, short context. Source recorded in live-ai/README.md.
RATES = {"gpt-6-luna": (100, 10, 500)}
LEASE_SECONDS = 45
# Full Luna context (922,000 input tokens), at most 3 requests and 1,200 output
# tokens/request. Stack long-context, cache-write, regional and Fast premiums:
# input/cache = 100 * 2 * 1.25 * 1.1 * 2; output = 500 * 1.5 * 1.1 * 2.
# The resulting 1,527,240,000 nano-USD envelope is rounded UP to $2 per ledger row.
CAPPED_PRICING_VERSION = "openai-conservative-2026-11-02-v1"
CAPPED_RATES = {"gpt-6-luna": (550, 550, 1650)}
RUN_RESERVATION_NANO = 2_000_000_000
CAPPED_VERSIONS = (CAPPED_PRICING_VERSION, BOUNDED_PRICING_VERSION)
GLOBAL_BUDGET_MAX_USD = Decimal(50)


def global_budget_nano(configured: float) -> int:
    value = Decimal(str(configured))
    if not value.is_finite() or value < 0:
        raise budget_unavailable()
    return int(min(value, GLOBAL_BUDGET_MAX_USD) * 1_000_000_000)


def liability_scope(at: datetime):
    """Carry yesterday through today's UTC day; retain unresolved liability across days.

    A turn can cross midnight (maximum runtime 120s). Carrying yesterday's complete
    ledger is deliberately conservative and avoids releasing its liability at midnight.
    """
    since = at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return or_(AiUsage.created_at >= since, AiUsage.state.in_(("open", "uncertain")))


def budget_unavailable() -> DomainError:
    return DomainError(503, "AI_BUDGET_UNAVAILABLE", "Chưa xác minh được giới hạn chi phí AI. Vui lòng thử lại sau.", True)


async def budget_liability(db, at: datetime) -> int:
    """Known conservative cost + reservations. Unknown relevant history fails closed."""
    relevant = liability_scope(at)
    legacy = AiUsage.pricing_version.not_in(CAPPED_VERSIONS)
    guest_owner = select(User.id).where(User.id == AiUsage.user_id, User.account_kind == "guest").exists()
    unknown = or_(
        AiUsage.estimated_nano_usd.is_(None), AiUsage.model.not_in(tuple(CAPPED_RATES)),
        and_(guest_owner, legacy, AiUsage.requests_started > 0),
        and_(legacy, or_(AiUsage.state != "settled",
                         AiUsage.requests_started != AiUsage.responses_received,
                         and_(AiUsage.requests_started > 0, AiUsage.input_tokens == 0))),
    )
    # Old standard-price settled rows are conservatively revalued without rewriting
    # historical audit metadata. Never assume their short-context estimate was a bound.
    cost = case((legacy, func.greatest(
        AiUsage.estimated_nano_usd,
        AiUsage.input_tokens * 550 + AiUsage.output_tokens * 1650,
    )), else_=AiUsage.estimated_nano_usd)
    # Guest usage is diagnostic metadata. Its detached reservation/totals are the
    # financial authority and survive deleting every guest identity and usage row.
    registered = select(User.id).where(User.id == AiUsage.user_id, User.account_kind != "guest").exists()
    from app.ai.search.accounting import external_liability_statement
    from app.modules.guests.accounting import detached_liability_statement
    from app.modules.guests.models import GuestBudgetDay

    # One database snapshot and round trip while the admission lock is held.
    # This retains every authority and fail-closed flag, including detached guest
    # and search liabilities; it does not cache money across transactions.
    unknown_rows, halted, total = (await db.execute(select(
        select(AiUsage.run_id).where(relevant, unknown).exists(),
        select(GuestBudgetDay.day).where(GuestBudgetDay.halted_at.is_not(None)).exists(),
        select(func.coalesce(func.sum(cost), 0)).where(relevant, registered).scalar_subquery()
        + detached_liability_statement(at).scalar_subquery()
        + external_liability_statement(at).scalar_subquery(),
    ))).one()
    if unknown_rows or halted:
        raise budget_unavailable()
    return int(total)


@dataclass
class UsageSnapshot:
    sequence: int = 0
    requests_started: int = 0
    responses_received: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    def observe(self, event: UsageEvent):
        if min(event.input_tokens, event.cached_input_tokens, event.output_tokens) < 0 or event.cached_input_tokens > event.input_tokens:
            raise ValueError("Invalid provider usage")
        self.sequence += 1
        self.requests_started += event.kind == "request_started"
        # Missing/zero usage is not a financially known response. Persist a mismatch,
        # so restart recovery cannot mistake an unpriced response for a free call.
        self.responses_received += event.kind == "response_received" and event.input_tokens > 0
        self.input_tokens += event.input_tokens
        self.cached_input_tokens += event.cached_input_tokens
        self.output_tokens += event.output_tokens
        self.tool_calls += event.kind == "tool_started"


async def reserve_accounting(db, run_id: UUID, user_id: UUID, worker_id: UUID, model: str, prompt_version: str, *, settings=None, guest_reservation_id=None):
    capped = settings is not None and settings.ai_daily_budget_usd > 0
    estimate, pricing_version = None, PRICING_VERSION
    rates = RATES.get(model)
    if capped:
        if not settings.ai_accounting_enabled or model not in CAPPED_RATES:
            raise budget_unavailable()
        # Same lock/order as user and proactive admission; transaction ends before
        # provider I/O. Concurrent processes cannot reserve the same remaining money.
        await db.execute(text("select pg_advisory_xact_lock(664201, 1)"))
        at = await db.scalar(select(func.clock_timestamp()))
        owner = await db.get(User, user_id)
        guest = owner is not None and owner.account_kind == "guest"
        bound = (BOUNDED_RESERVATION_NANO if settings.ai_bounded_reservations_enabled and not guest else RUN_RESERVATION_NANO)
        liability = await budget_liability(db, at)
        ceiling = global_budget_nano(settings.ai_daily_budget_usd)
        # Proactive descendants must also leave the interactive share untouched.
        run = await db.get(AiRun, run_id)
        ancestor = run
        while ancestor is not None and ancestor.parent_run_id is not None:
            ancestor = await db.get(AiRun, ancestor.parent_run_id)
        if ancestor is not None and ancestor.origin == "proactive":
            ceiling = int(Decimal(ceiling) * Decimal(str(settings.proactive_budget_share)))
        guest_upper = None
        if guest:
            from app.modules.guests.models import GuestCostReservation, GuestOperationLink
            from app.modules.guests.pricing import ai_upper, kind_available

            guest_upper = await db.scalar(select(GuestCostReservation.upper_nano_usd).join(
                GuestOperationLink, GuestOperationLink.reservation_id == GuestCostReservation.id).where(
                    GuestCostReservation.id == guest_reservation_id, GuestCostReservation.state == "reserved",
                    GuestOperationLink.user_id == user_id, GuestCostReservation.kind == "ai"))
            required = ai_upper(settings.guest_pricing_json)
            if (not kind_available(settings, "ai") or required is None or guest_upper is None
                    or guest_upper < required[1]):
                raise budget_unavailable()
        if liability + (0 if guest else bound) > ceiling:
            raise DomainError(503, "AI_BUDGET_EXHAUSTED", "AI đã đạt giới hạn sử dụng. Vui lòng thử lại sau.", True)
        rates, estimate = CAPPED_RATES[model], guest_upper if guest else bound
        pricing_version = BOUNDED_PRICING_VERSION if settings.ai_bounded_reservations_enabled and not guest else CAPPED_PRICING_VERSION
    db.add(AiUsage(run_id=run_id, user_id=user_id, worker_id=worker_id,
                   model=model, prompt_version=prompt_version, pricing_version=pricing_version,
                   estimated_nano_usd=estimate,
                   input_nano_rate=rates[0] if rates else None,
                   cached_nano_rate=rates[1] if rates else None,
                   output_nano_rate=rates[2] if rates else None,
                   lease_until=now() + timedelta(seconds=LEASE_SECONDS)))
    await db.flush()


async def persist_snapshot(db, run_id: UUID, worker_id: UUID, snapshot: UsageSnapshot, *, terminal: bool = False) -> bool:
    row = await db.scalar(select(AiUsage).where(
        AiUsage.run_id == run_id, AiUsage.worker_id == worker_id,
        AiUsage.lease_until > func.now(),
    ).with_for_update())
    if row is None or snapshot.sequence < row.sequence:
        return False
    state = ("uncertain" if snapshot.requests_started != snapshot.responses_received else "settled") if terminal else "open"
    if row.state != "open":
        return row.sequence == snapshot.sequence and row.state == state
    if any(getattr(snapshot, field) < getattr(row, field) for field in (
        "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens", "tool_calls",
    )):
        return False
    for field in ("sequence", "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens", "tool_calls"):
        setattr(row, field, getattr(snapshot, field))
    row.state = state
    row.lease_until = now() + timedelta(seconds=LEASE_SECONDS)
    input_rate, cached_rate, output_rate = row.input_nano_rate, row.cached_nano_rate, row.output_nano_rate
    capped = row.pricing_version in CAPPED_VERSIONS
    if input_rate is not None and cached_rate is not None and output_rate is not None and (
        not capped or state == "settled"
    ):
        row.estimated_nano_usd = ((snapshot.input_tokens - snapshot.cached_input_tokens) * input_rate
                                  + snapshot.cached_input_tokens * cached_rate
                                  + snapshot.output_tokens * output_rate)
    await db.flush()
    return True


async def recover_expired(db):
    # Never replay a provider call or touch another worker's unexpired lease.
    # Keep the same usage → run lock order as terminal settlement.
    expired = (await db.scalars(select(AiUsage.run_id).where(
        AiUsage.state == "open", AiUsage.lease_until <= func.now(),
    ).order_by(AiUsage.run_id).limit(1000).with_for_update(skip_locked=True))).all()
    if not expired:
        return
    await db.execute(update(AiRun).where(AiRun.status == "running", AiRun.id.in_(expired)).values(status="interrupted", version=2))
    await db.execute(update(AiUsage).where(AiUsage.state == "open", AiUsage.run_id.in_(expired)).values(
        state=case((AiUsage.requests_started == AiUsage.responses_received, "settled"), else_="uncertain"),
        # On a crashed worker, only definite no-dispatch can release a reservation.
        estimated_nano_usd=case((and_(AiUsage.pricing_version.in_(CAPPED_VERSIONS),
                                              AiUsage.requests_started == 0), 0),
                               else_=AiUsage.estimated_nano_usd),
    ))
