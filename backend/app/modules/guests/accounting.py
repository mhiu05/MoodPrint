"""Detached daily guest liability: atomic reservations that survive every guest purge.

Integer nano-USD, no owner link in the durable rows. ``guest_budget_days`` and
``guest_cost_reservations`` hold no user, run, provider, session or address, so purging every guest
can never reopen a spent budget, and a late settlement never recreates a user-linked row. Lock
order (canonical): owner -> admission -> usage -> budget day -> reservation -> operation link. A
settlement that holds only budget/reservation locks never then takes a user or link lock.

Uncertain outcomes (timeout, crash, missing usage, a worker that died between the dispatched
marker and the network) are charged at the reserved upper bound exactly once and never refunded.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import digest
from app.infrastructure.database.models import User
from app.modules.guests.limits import BANGKOK
from app.modules.guests.models import GuestBudgetDay, GuestCostReservation, GuestOperationLink
from app.modules.guests.policy import database_time

log = logging.getLogger("moodprint")


@dataclass(frozen=True)
class Reservation:
    id: UUID
    upper_nano_usd: int


def unavailable() -> DomainError:
    return DomainError(
        503,
        "GUEST_PAID_UNAVAILABLE",
        "Tính năng này chưa mở cho lượt dùng thử. Bạn vẫn có thể ghi nhật ký và đổi tâm trạng.",
    )


def exhausted() -> DomainError:
    return DomainError(
        429,
        "GUEST_BUDGET_EXHAUSTED",
        "Hôm nay lượt dùng thử đã đạt giới hạn chung. Vui lòng quay lại vào ngày mai.",
        True,
    )


async def _today(db: AsyncSession) -> date:
    return (await database_time(db)).astimezone(BANGKOK).date()


async def reserve_guest_operation(
    db: AsyncSession,
    user: User,
    kind: str,
    upper_cost: int,
    *,
    operation_key: str,
    payload_digest: str,
    limit_nano_usd: int,
    lease_seconds: int = 120,
) -> Reservation:
    """Reserve the worst case before any paid dispatch; idempotent for one operation key."""
    if upper_cost <= 0 or limit_nano_usd <= 0:
        raise unavailable()
    key_hash = digest(operation_key)
    link = await db.get(GuestOperationLink, (user.id, kind, key_hash))
    if link is not None and link.reservation_id is not None:
        if link.payload_digest != payload_digest:
            raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Mã thao tác đã được dùng với nội dung khác.")
        existing = await db.get(GuestCostReservation, link.reservation_id)
        if existing is not None:
            return Reservation(existing.id, existing.upper_nano_usd)
    # A halted (overrun) day blocks paid admissions on every later day until an operator reviews it.
    if await db.scalar(select(GuestBudgetDay.day).where(GuestBudgetDay.halted_at.is_not(None)).limit(1)):
        raise unavailable()
    today = await _today(db)
    # The configured limit may be raised (with approval) but spent/reserved are never reset.
    await db.execute(
        insert(GuestBudgetDay)
        .values(day=today, limit_nano_usd=limit_nano_usd)
        .on_conflict_do_update(
            index_elements=[GuestBudgetDay.day], set_={"limit_nano_usd": limit_nano_usd}
        )
    )
    day = await db.scalar(
        select(GuestBudgetDay).where(GuestBudgetDay.day == today).with_for_update()
    )
    assert day is not None
    if day.spent_nano_usd + day.reserved_nano_usd + upper_cost > day.limit_nano_usd:
        raise exhausted()
    now = await database_time(db)
    reservation = GuestCostReservation(
        id=uuid4(), day=today, kind=kind, upper_nano_usd=upper_cost, state="reserved"
    )
    reservation.lease_until = now + timedelta(seconds=lease_seconds)
    db.add(reservation)
    day.reserved_nano_usd += upper_cost
    await db.flush()
    if link is not None:
        link.reservation_id = reservation.id
    else:
        db.add(
            GuestOperationLink(
                user_id=user.id,
                kind=kind,
                operation_key_hash=key_hash,
                payload_digest=payload_digest,
                reservation_id=reservation.id,
                state="claimed",
                worker_id=uuid4(),
                lease_token=uuid4(),
                lease_until=reservation.lease_until,
            )
        )
    await db.flush()
    return Reservation(reservation.id, upper_cost)


async def mark_guest_dispatched(db: AsyncSession, reservation_id: UUID) -> None:
    """Persist 'about to dispatch' BEFORE the provider call; a crash after this charges the bound."""
    _day, row = await _locked(db, reservation_id)
    now = await database_time(db)
    if row is None or row.state != "reserved" or row.lease_until <= now:
        raise DomainError(409, "GUEST_OPERATION_FENCED", "Lượt xử lý đã kết thúc. Hãy thử một yêu cầu mới.")
    row.state, row.dispatched_at = "dispatched", now
    await db.execute(
        update(GuestOperationLink)
        .where(GuestOperationLink.reservation_id == reservation_id)
        .values(state="dispatched")
    )


async def _locked(db: AsyncSession, reservation_id: UUID):
    # Read the day without a lock, then lock budget and reservation in canonical order.
    day_id = await db.scalar(select(GuestCostReservation.day).where(GuestCostReservation.id == reservation_id))
    if day_id is None:
        return None, None
    day = await db.scalar(
        select(GuestBudgetDay).where(GuestBudgetDay.day == day_id).with_for_update().execution_options(populate_existing=True)
    )
    reservation = await db.scalar(
        select(GuestCostReservation)
        .where(GuestCostReservation.id == reservation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return day, reservation


async def release_guest_operation(db: AsyncSession, reservation_id: UUID) -> None:
    """Definite no-dispatch only (admission rejected before any send): release once."""
    day, reservation = await _locked(db, reservation_id)
    if day is None or reservation is None or reservation.state != "reserved":
        return
    day.reserved_nano_usd -= reservation.upper_nano_usd
    reservation.state = "cancelled"


async def settle_guest_operation(
    db: AsyncSession, reservation: Reservation | UUID, actual_or_uncertain: int | None
) -> None:
    """Settle exactly once. ``None`` (uncertain) charges the full reserved upper bound.

    Known actual <= upper: release the reservation, add the actual. Actual > upper is an
    accounting incident: charge the actual and halt paid admissions across days until reviewed.
    A repeated settlement is a no-op (an uncertain charge is never reduced by a late actual).
    """
    reservation_id = reservation.id if isinstance(reservation, Reservation) else reservation
    day, row = await _locked(db, reservation_id)
    if day is None or row is None or row.state not in ("reserved", "dispatched"):
        return
    day.reserved_nano_usd -= row.upper_nano_usd
    if actual_or_uncertain is None:
        day.spent_nano_usd += row.upper_nano_usd
        row.charged_nano_usd, row.state = row.upper_nano_usd, "uncertain"
        return
    actual = max(0, actual_or_uncertain)
    day.spent_nano_usd += actual
    row.charged_nano_usd, row.state = actual, "settled"
    if actual > row.upper_nano_usd:
        day.halted_at = await database_time(db)
        log.error("metric=guest_budget_overrun kind=%s", row.kind)


async def settle_open_for_user(db: AsyncSession, user_id: UUID) -> int:
    """Purge hook: conservatively settle every unsettled reservation linked to this guest."""
    ids = (
        await db.scalars(
            select(GuestOperationLink.reservation_id).where(
                GuestOperationLink.user_id == user_id,
                GuestOperationLink.reservation_id.is_not(None),
            )
        )
    ).all()
    settled = 0
    for reservation_id in ids:
        if reservation_id is None:
            continue
        probe = await db.get(GuestCostReservation, reservation_id)
        if probe is None or probe.state not in ("reserved", "dispatched"):
            continue
        if probe.state == "reserved":
            await release_guest_operation(db, reservation_id)
        else:
            await settle_guest_operation(db, reservation_id, None)
        settled += 1
    return settled


async def settle_stale_reservations(db: AsyncSession, limit: int = 50) -> int:
    """Restart/lease recovery: a stale dispatched reservation is charged uncertain, never replayed."""
    now = await database_time(db)
    rows = (
        await db.scalars(
            select(GuestCostReservation.id)
            .where(
                GuestCostReservation.state.in_(("reserved", "dispatched")),
                GuestCostReservation.lease_until < now,
            )
            .order_by(GuestCostReservation.lease_until)
            .limit(limit)
        )
    ).all()
    for reservation_id in rows:
        probe = await db.get(GuestCostReservation, reservation_id)
        if probe is None:
            continue
        if probe.state == "reserved":
            await release_guest_operation(db, reservation_id)
        else:
            await settle_guest_operation(db, reservation_id, None)
    return len(rows)
