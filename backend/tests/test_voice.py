import io
import wave
from uuid import uuid4

import pytest


def audio(seconds=1, rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * rate * seconds)
    return output.getvalue()


def test_audio_duration_is_verified_from_pcm_data_not_client_metadata():
    from app.core.errors import DomainError
    from app.modules.voice.service import validate_audio

    assert validate_audio(audio(30)) == 30
    for invalid in (audio(31), b"not-a-wav", audio(1)[:-500]):
        with pytest.raises(DomainError):
            validate_audio(invalid)


@pytest.mark.postgres
async def test_voice_requires_both_consents_and_rechecks_before_returning_preview(clients):
    app, actors = clients
    a, _ = actors[0]
    payload = audio()
    headers = {"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())}
    result = await a.post("/api/v1/voice/transcriptions", content=payload, headers=headers)
    assert result.status_code == 403
    for purpose in ("AI", "VOICE"):
        await a.put(
            f"/api/v1/consents/{purpose}",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
            headers={"Idempotency-Key": str(uuid4())},
        )

    class SyntheticTranscriber:
        async def transcribe(self, data):
            assert data == payload
            return "Bản chữ để bạn duyệt"

    app.state.transcriber = SyntheticTranscriber()
    result = await a.post("/api/v1/voice/transcriptions", content=payload, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["text"] == "Bản chữ để bạn duyệt"
    assert "sent" not in result.json()
