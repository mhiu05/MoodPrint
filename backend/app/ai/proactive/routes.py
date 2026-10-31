"""Check-in settings and schedules (P1-10). Every write locks the account row first."""

from datetime import time, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from app.ai.proactive import schedule as math
from app.ai.proactive.models import (
    POLICY_VERSION,
    AiProactiveJob,
    AiProactiveSchedule,
    AiProactiveSettings,
)
from app.ai.proactive.policy import available, eligibility_reason, match_enabled
from app.ai.proactive.schemas import (
    Eligibility,
    ProactiveLimits,
    ProactiveSettingsInput,
    ProactiveSettingsView,
    ProactiveView,
    ScheduleInput,
    ScheduleView,
    Slot,
)
from app.contracts import ActionReceipt, BotId, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_registered_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AiRun, User, now

router = APIRouter()
BOT_ORDER = ("nhip", "rure", "may", "guong", "caunoi")
MAX_PAUSE_DAYS = 30
UNSTARTED = ("pending", "retry")


def _hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def _time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _unavailable() -> DomainError:
    return DomainError(
        503, "PROACTIVE_UNAVAILABLE", "Lời hỏi thăm đang tạm nghỉ. Bạn thử lại sau nhé.", True
    )


def _stale(what: str) -> DomainError:
    return DomainError(
        409, "STALE_VERSION", f"{what} vừa được thay đổi ở nơi khác. Mình đã tải lại để bạn xem."
    )


def settings_view(prefs: AiProactiveSettings | None, user: User) -> ProactiveSettingsView:
    if prefs is None:
        start, end = math.default_quiet_hours(user.age_band)
        return ProactiveSettingsView(
            timezone=user.timezone, quiet_start=_hhmm(start), quiet_end=_hhmm(end),
            badges_enabled=True, journal_context_enabled=False, version=0,
            policy_version=POLICY_VERSION,
        )
    return ProactiveSettingsView(
        timezone=prefs.timezone, quiet_start=_hhmm(prefs.quiet_start),
        quiet_end=_hhmm(prefs.quiet_end), badges_enabled=prefs.badges_enabled,
        journal_context_enabled=prefs.journal_context_enabled, version=prefs.version,
        policy_version=prefs.policy_version,
    )


def schedule_view(
    row: AiProactiveSchedule | None, bot_id: str, slot: str, user: User, reason: str | None
) -> ScheduleView:
    eligibility = Eligibility(allowed=reason is None, reason=reason)  # type: ignore[arg-type]
    if row is None:
        return ScheduleView(
            bot_id=bot_id, slot=slot, enabled=False,  # type: ignore[arg-type]
            local_time=_hhmm(math.default_time(slot, user.age_band)), weekdays=list(range(1, 8)),
            version=0, eligibility=eligibility,
        )
    return ScheduleView(
        bot_id=row.bot_id, slot=row.slot, enabled=row.enabled,  # type: ignore[arg-type]
        local_time=_hhmm(row.local_time), weekdays=math.mask_to_weekdays(row.weekdays),
        paused_until=row.paused_until, auto_paused=row.auto_paused_at is not None,
        next_delivery_at=row.next_due_at if row.enabled and row.auto_paused_at is None else None,
        version=row.version, eligibility=eligibility,
    )


async def _schedules(db, user_id: UUID) -> dict[tuple[str, str], AiProactiveSchedule]:
    rows = (
        await db.scalars(select(AiProactiveSchedule).where(AiProactiveSchedule.user_id == user_id))
    ).all()
    return {(row.bot_id, row.slot): row for row in rows}


async def cancel_unstarted(db, user_id: UUID, *, schedule_id: UUID | None = None,
                           bot_id: str | None = None) -> None:
    """Cancel jobs no worker has claimed. Running jobs are fenced by version checks at publish."""
    statement = update(AiProactiveJob).where(
        AiProactiveJob.user_id == user_id, AiProactiveJob.status.in_(UNSTARTED)
    )
    if schedule_id is not None:
        statement = statement.where(AiProactiveJob.schedule_id == schedule_id)
    if bot_id is not None:
        statement = statement.where(AiProactiveJob.bot_id == bot_id)
    await db.execute(statement.values(status="cancelled", finished_at=now(), last_error="changed"))


def _next_due(row: AiProactiveSchedule, timezone: str):
    if not row.enabled:
        return None
    return math.next_occurrence(
        local_time=row.local_time, weekdays=row.weekdays, paused_until=row.paused_until,
        timezone=timezone, after=now(),
    )


async def _view(request: Request, db, user: User) -> ProactiveView:
    settings = request.app.state.settings
    prefs = await db.get(AiProactiveSettings, user.id)
    rows = await _schedules(db, user.id)
    match = await match_enabled(db, user)
    schedules = [
        schedule_view(
            rows.get((bot, slot)), bot, slot, user,
            eligibility_reason(settings=settings, user=user, bot_id=bot, match=match),
        )
        for bot in BOT_ORDER
        for slot in math.SLOTS
    ]
    return ProactiveView(
        available=available(settings, request.app.state.ai, user),
        settings=settings_view(prefs, user),
        schedules=schedules,
        limits=ProactiveLimits(
            daily_cap=settings.proactive_daily_cap_per_user,
            enabled_slots=sum(row.enabled for row in rows.values()),
            windows={
                slot: [_hhmm(edge) for edge in math.window_for(slot, user.age_band)]
                for slot in math.SLOTS
            },
            step_minutes=math.STEP_MINUTES,
        ),
    )


def _default_settings(user: User) -> AiProactiveSettings:
    start, end = math.default_quiet_hours(user.age_band)
    return AiProactiveSettings(
        user_id=user.id, timezone=user.timezone, quiet_start=start, quiet_end=end,
        badges_enabled=True, journal_context_enabled=False, journal_context_version=0,
        version=1, policy_version=POLICY_VERSION,
    )


@router.get("/ai/proactive", response_model=ProactiveView)
async def proactive(request: Request, actor: Actor = Depends(require_registered_actor)):
    async with transaction(request, actor, lock=False) as (db, user):
        return await _view(request, db, user)


@router.put("/ai/proactive/schedules/{bot_id}/{slot}", response_model=ScheduleView)
async def save_schedule(
    bot_id: BotId,
    slot: Slot,
    body: ScheduleInput,
    request: Request,
    actor: Actor = Depends(require_registered_actor),
):
    settings = request.app.state.settings
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"proactive:schedule:{bot_id}:{slot}"
    async with transaction(request, actor) as (db, user):
        if not available(settings, request.app.state.ai, user):
            raise _unavailable()
        rows = await _schedules(db, user.id)
        row = rows.get((bot_id, slot))
        prefs = await db.get(AiProactiveSettings, user.id)
        match = await match_enabled(db, user)
        reason = eligibility_reason(settings=settings, user=user, bot_id=bot_id, match=match)
        if await previous_receipt(db, user, operation, key, payload):
            return schedule_view(row, bot_id, slot, user, reason)
        if (row.version if row else 0) != body.expected_version:
            raise _stale("Lịch")
        local_time = _time(body.local_time)
        if not math.time_allowed(slot, local_time, user.age_band):
            evening_end = _hhmm(math.window_for("evening", user.age_band)[1])
            raise DomainError(
                422, "SCHEDULE_WINDOW",
                f"Buổi sáng chọn từ 5:00 đến 11:30, buổi tối từ 17:00 đến {evening_end}.",
            )
        if prefs is None:
            prefs = _default_settings(user)
            db.add(prefs)
        today = math.local_date(now(), prefs.timezone)
        paused = body.paused_until if body.paused_until and body.paused_until >= today else None
        if paused and paused > today + timedelta(days=MAX_PAUSE_DAYS):
            raise DomainError(422, "SCHEDULE_PAUSE", "Chỉ tạm dừng tối đa 30 ngày.")
        if body.enabled:
            if reason is not None:
                raise DomainError(
                    403, "PROACTIVE_INELIGIBLE",
                    "Trợ lý này chưa thể hỏi thăm với tài khoản hiện tại.",
                )
            if math.quiet_conflict(local_time, prefs.quiet_start, prefs.quiet_end):
                raise DomainError(
                    422, "SCHEDULE_IN_QUIET_HOURS",
                    "Giờ này nằm trong giờ yên lặng của bạn. Chọn giờ khác hoặc đổi giờ yên lặng.",
                )
            others = sum(r.enabled for pair, r in rows.items() if pair != (bot_id, slot))
            cap = settings.proactive_daily_cap_per_user
            if not math.within_cap(enabled_after=others + 1, cap=cap):
                raise DomainError(
                    409, "PROACTIVE_DAILY_CAP",
                    f"Bạn đã dùng {cap} lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này.",
                )
        if row is None:
            row = AiProactiveSchedule(user_id=user.id, bot_id=bot_id, slot=slot, version=0)
            db.add(row)
        row.enabled, row.local_time, row.paused_until = body.enabled, local_time, paused
        row.weekdays = math.weekdays_to_mask(body.weekdays)
        if body.enabled:
            # Turning a check-in on again (or editing it) is a clear sign it is wanted.
            row.auto_paused_at = None
        row.version += 1
        row.updated_at = now()
        row.next_due_at = _next_due(row, prefs.timezone)
        await db.flush()
        await cancel_unstarted(db, user.id, schedule_id=row.id)
        # last_seen_at is otherwise written only by the 15-minute session slide.
        user.last_seen_at = now()
        save_receipt(db, user, operation, key, payload, {"version": row.version})
        return schedule_view(row, bot_id, slot, user, reason)


@router.delete("/ai/proactive/schedules/{bot_id}/{slot}", response_model=ActionReceipt)
async def delete_schedule(
    bot_id: BotId,
    slot: Slot,
    body: VersionInput,
    request: Request,
    actor: Actor = Depends(require_registered_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"proactive:delete:{bot_id}:{slot}"
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        row = (await _schedules(db, user.id)).get((bot_id, slot))
        if row is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy lịch hỏi thăm.")
        if row.version != body.expected_version:
            raise _stale("Lịch")
        await cancel_unstarted(db, user.id, schedule_id=row.id)
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=f"{bot_id}:{slot}", resource_version=row.version
        )
        await db.delete(row)
        user.last_seen_at = now()
        save_receipt(db, user, operation, key, payload, receipt.model_dump(mode="json", by_alias=True))
        return receipt


@router.put("/ai/proactive/settings", response_model=ProactiveSettingsView)
async def save_settings(
    body: ProactiveSettingsInput, request: Request, actor: Actor = Depends(require_registered_actor)
):
    settings = request.app.state.settings
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    revoked = False
    async with transaction(request, actor) as (db, user):
        if not available(settings, request.app.state.ai, user):
            raise _unavailable()
        prefs = await db.get(AiProactiveSettings, user.id)
        if await previous_receipt(db, user, "proactive:settings", key, payload):
            return settings_view(prefs, user)
        if (prefs.version if prefs else 0) != body.expected_version:
            raise _stale("Cài đặt")
        if not math.timezone_valid(body.timezone):
            raise DomainError(422, "INVALID_TIMEZONE", "Múi giờ chưa hợp lệ.")
        quiet_start, quiet_end = _time(body.quiet_start), _time(body.quiet_end)
        if not math.quiet_hours_valid(quiet_start, quiet_end):
            raise DomainError(
                422, "QUIET_HOURS_INVALID", "Giờ yên lặng cần dài từ 4 đến 12 tiếng, theo bước 15 phút."
            )
        rows = (await _schedules(db, user.id)).values()
        if any(r.enabled and math.quiet_conflict(r.local_time, quiet_start, quiet_end) for r in rows):
            raise DomainError(
                409, "SCHEDULE_IN_QUIET_HOURS",
                "Một lời hỏi thăm đang bật nằm trong giờ yên lặng mới. Đổi giờ hỏi thăm trước nhé.",
            )
        if prefs is None:
            prefs = _default_settings(user)
            prefs.version = 0
            db.add(prefs)
        timing_changed = (prefs.timezone, prefs.quiet_start, prefs.quiet_end) != (
            body.timezone, quiet_start, quiet_end
        )
        revoked = prefs.journal_context_enabled and not body.journal_context_enabled
        prefs.timezone, prefs.quiet_start, prefs.quiet_end = body.timezone, quiet_start, quiet_end
        prefs.badges_enabled = body.badges_enabled
        prefs.journal_context_enabled = body.journal_context_enabled
        prefs.policy_version = body.policy_version
        prefs.version += 1
        prefs.updated_at = now()
        if revoked:
            # Old journal-derived check-ins stop being context immediately (revalidation
            # compares this version), and every in-flight derivative is cut by data_version.
            prefs.journal_context_version += 1
            user.data_version += 1
            await db.execute(
                update(AiRun)
                .where(AiRun.user_id == user.id, AiRun.status == "running")
                .values(status="cancelled", version=2)
            )
            await cancel_unstarted(db, user.id, bot_id="nhip")
        if timing_changed:
            for row in rows:
                row.next_due_at = _next_due(row, prefs.timezone)
                row.updated_at = now()
            await cancel_unstarted(db, user.id)
        user.last_seen_at = now()
        await db.flush()
        save_receipt(db, user, "proactive:settings", key, payload, {"version": prefs.version})
        result = settings_view(prefs, user)
    if revoked:
        request.app.state.ai.invalidate(str(actor.user_id))
    return result

