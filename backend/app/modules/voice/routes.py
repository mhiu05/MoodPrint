import asyncio
import hashlib

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from app.contracts import DTO
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.core.security import Actor, assert_purpose, idempotency_key, require_actor, transaction
from app.core.streams import StreamSlots
from app.modules.guests.accounting import (
    mark_guest_dispatched,
    release_guest_operation,
    reserve_guest_operation,
    settle_guest_operation,
)
from app.modules.guests.accounting import unavailable as guest_paid_unavailable
from app.modules.guests.deadlines import guard_guest_dispatch
from app.modules.guests.limits import finish_guest_quota, maintain_guest_quota, reserve_guest_quota
from app.modules.guests.policy import guest_expired, guest_paid_available
from app.modules.guests.pricing import budget_nano, voice_upper
from app.modules.voice.service import validate_audio

router = APIRouter()
VOICE_LIMITED = ("VOICE_RATE_LIMITED", "Bạn đã gửi nhiều bản ghi âm. Vui lòng đợi một chút.")
VOICE_LIMIT = AttemptLimiter(6, 60, *VOICE_LIMITED)
VOICE_DAILY_LIMIT = AttemptLimiter(60, 86_400, *VOICE_LIMITED)
VOICE_SLOTS = StreamSlots(1)


class TranscriptionPreview(DTO):
    text: str = Field(max_length=500)
    duration_seconds: float


@router.post("/voice/transcriptions", response_model=TranscriptionPreview)
async def transcribe(request: Request, actor: Actor = Depends(require_actor)):
    key = idempotency_key(request)
    guest = actor.account_kind == "guest"
    settings = request.app.state.settings
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "VOICE")
        version = user.data_version
    if guest and not guest_paid_available(settings, "voice"):
        # Fail closed: no approved budget/price means no paid guest transcription at all.
        raise guest_paid_unavailable()
    provider = request.app.state.transcriber
    if provider is None or (
        request.app.state.settings.ai_local_test_user_ids
        and not request.app.state.ai.available_for(actor.user_id)
    ):
        raise DomainError(503, "VOICE_UNAVAILABLE", "Chuyển giọng nói thành chữ chưa sẵn sàng.")
    if request.headers.get("Content-Type", "").split(";")[0] != "audio/wav":
        raise DomainError(422, "INVALID_AUDIO", "Chỉ nhận định dạng WAV.")
    # Each accepted upload is a paid provider call: bound rate and concurrency per user.
    VOICE_LIMIT.check("minute:" + str(actor.user_id))
    VOICE_DAILY_LIMIT.check("day:" + str(actor.user_id))
    release = VOICE_SLOTS.reserve(actor.user_id)
    audio = bytearray()
    task: asyncio.Task[str] | None = None
    # Guest bound (None for registered users): every stage below may only shorten work.
    bound = getattr(request.state, "guest_output", None)
    budget = 35.0
    reservation = quota = None
    dispatched = False
    result_known = False

    def expired() -> bool:
        return bound is not None and bound.remaining() <= 0

    try:
        async for chunk in request.stream():
            if expired():
                raise guest_expired()
            if len(audio) + len(chunk) > 3_000_000:
                raise DomainError(413, "AUDIO_TOO_LARGE", "Bản ghi âm quá lớn.")
            audio.extend(chunk)
        duration = validate_audio(bytes(audio))
        if guest:
            # One transaction: lifetime quota claim + worst-case reservation, before any send.
            upper = voice_upper(settings.guest_pricing_json, duration)
            if upper is None:
                raise guest_paid_unavailable()
            clip = hashlib.sha256(bytes(audio)).hexdigest()
            async with transaction(request, actor) as (db, user):
                quota = await reserve_guest_quota(
                    db,
                    user,
                    kind="voice",
                    operation_key=key,
                    payload_digest=clip,
                    settings=settings,
                    voice_milliseconds=int(duration * 1000),
                )
                reservation = await reserve_guest_operation(
                    db,
                    user,
                    "voice",
                    upper[1],
                    operation_key=key,
                    payload_digest=clip,
                    limit_nano_usd=budget_nano(settings.guest_daily_budget_usd) or 0,
                )
        async with maintain_guest_quota(request.app.state.database, actor.user_id, "voice", quota):
            # Fresh database decision, then a synchronous check immediately before dispatch.
            await guard_guest_dispatch(request.app.state.database, actor)
            if reservation is not None:
                async with request.app.state.database.require()() as db, db.begin():
                    await mark_guest_dispatched(db, reservation.id)
                dispatched = True
            if expired():
                raise guest_expired()
            task = asyncio.create_task(provider.transcribe(bytes(audio)))
            budget = 35.0 if bound is None else min(35.0, max(0.0, bound.remaining()))
            async with asyncio.timeout(budget):
                while not task.done():
                    await asyncio.wait({task}, timeout=0.5)
                    if expired():
                        raise guest_expired()
                    if not task.done():
                        async with transaction(request, actor) as (db, user):
                            await assert_purpose(db, user, "VOICE")
                            if user.data_version != version:
                                raise DomainError(409, "CONTEXT_CHANGED", "Quyền đã thay đổi. Bản ghi âm đã dừng xử lý.")
                text = await task
            result_known = True
            async with transaction(request, actor) as (db, user):
                await assert_purpose(db, user, "VOICE")
                if user.data_version != version:
                    raise DomainError(
                        409, "CONTEXT_CHANGED", "Quyền đã thay đổi. Bản chữ không được sử dụng."
                    )
            if expired():
                # The provider answered after T: discard the transcript, never return it.
                raise guest_expired()
            if not isinstance(text, str) or len(text) > 500:
                raise DomainError(
                    422, "TRANSCRIPT_TOO_LONG", "Bản chữ quá dài. Hãy ghi một đoạn ngắn hơn."
                )
            return TranscriptionPreview(text=text, duration_seconds=duration)
    except DomainError:
        raise
    except (Exception, TimeoutError) as exc:
        if expired() or (isinstance(exc, TimeoutError) and bound is not None and budget < 35.0):
            # The clamped budget ran out because the trial ended (a timer may fire a clock tick
            # early): report that, not a provider fault.
            raise guest_expired() from None
        raise DomainError(
            503,
            "TRANSCRIPTION_FAILED",
            "Chưa chuyển được giọng nói thành chữ. Bạn vẫn có thể nhập tin nhắn.",
            True,
        ) from exc
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if reservation is not None:
            try:
                async with request.app.state.database.require()() as db, db.begin():
                    if not dispatched:
                        await release_guest_operation(db, reservation.id)
                    else:
                        # The billed duration was reserved exactly; an unknown outcome is uncertain.
                        await settle_guest_operation(
                            db, reservation, reservation.upper_nano_usd if result_known else None
                        )
                if quota is not None:
                    async with request.app.state.database.require()() as db, db.begin():
                        await finish_guest_quota(
                            db, actor.user_id, "voice", quota.operation_key_hash, quota.lease_token
                        )
            except Exception:  # the stale-reservation sweep charges it uncertain
                pass
        release()
        audio.clear()
