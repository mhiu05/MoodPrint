import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from app.contracts import DTO
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.core.security import Actor, assert_purpose, idempotency_key, require_actor, transaction
from app.core.streams import StreamSlots
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
    idempotency_key(request)
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "VOICE")
        version = user.data_version
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
    try:
        async for chunk in request.stream():
            if len(audio) + len(chunk) > 3_000_000:
                raise DomainError(413, "AUDIO_TOO_LARGE", "Bản ghi âm quá lớn.")
            audio.extend(chunk)
        duration = validate_audio(bytes(audio))
        task = asyncio.create_task(provider.transcribe(bytes(audio)))
        async with asyncio.timeout(35):
            while not task.done():
                await asyncio.wait({task}, timeout=0.5)
                if not task.done():
                    async with transaction(request, actor) as (db, user):
                        await assert_purpose(db, user, "VOICE")
                        if user.data_version != version:
                            raise DomainError(409, "CONTEXT_CHANGED", "Quyền đã thay đổi. Bản ghi âm đã dừng xử lý.")
            text = await task
        async with transaction(request, actor) as (db, user):
            await assert_purpose(db, user, "VOICE")
            if user.data_version != version:
                raise DomainError(
                    409, "CONTEXT_CHANGED", "Quyền đã thay đổi. Bản chữ không được sử dụng."
                )
        if not isinstance(text, str) or len(text) > 500:
            raise DomainError(
                422, "TRANSCRIPT_TOO_LONG", "Bản chữ quá dài. Hãy ghi một đoạn ngắn hơn."
            )
        return TranscriptionPreview(text=text, duration_seconds=duration)
    except DomainError:
        raise
    except (Exception, TimeoutError) as exc:
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
        release()
        audio.clear()
