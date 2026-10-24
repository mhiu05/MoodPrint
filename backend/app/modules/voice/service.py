import io
import wave

from openai import AsyncOpenAI

from app.core.errors import DomainError


def validate_audio(data: bytes) -> float:
    if not data or len(data) > 3_000_000:
        raise DomainError(422, "INVALID_AUDIO", "Bản ghi âm quá lớn hoặc không hợp lệ.")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            rate, frames = wav.getframerate(), wav.getnframes()
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getcomptype() != "NONE"
                or not 8000 <= rate <= 48000
            ):
                raise ValueError("Unsupported PCM format")
            duration = frames / rate
            if not 0 < duration <= 30 or len(wav.readframes(frames)) != frames * 2:
                raise ValueError("Truncated or overlong recording")
    except (wave.Error, EOFError, ValueError, ZeroDivisionError) as exc:
        raise DomainError(
            422, "INVALID_AUDIO", "Chỉ nhận bản ghi âm WAV mono tối đa 30 giây."
        ) from exc
    return duration


class OpenAITranscriber:
    def __init__(self, settings):
        self.key = settings.openai_api_key
        self.model = settings.stt_model

    async def transcribe(self, data: bytes) -> str:
        async with AsyncOpenAI(
            api_key=self.key.get_secret_value(), max_retries=0, timeout=30
        ) as client:
            result = await client.audio.transcriptions.create(
                file=("recording.wav", data, "audio/wav"), model=self.model, response_format="json"
            )
        return result.text
