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


@pytest.mark.postgres
async def test_local_voice_enablement_denies_an_actor_outside_the_live_scope(clients):
    app, actors = clients
    app.state.settings.app_env = "development"
    app.state.settings.ai_local_test_user_ids = [actors[0][1]]
    outsider = actors[1][0]
    for purpose in ("AI", "VOICE"):
        await outsider.put(f"/api/v1/consents/{purpose}", json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"}, headers={"Idempotency-Key": str(uuid4())})
    calls = []

    class Transcriber:
        async def transcribe(self, data):
            calls.append(True)
            return "must not run"

    app.state.transcriber = Transcriber()
    session = (await outsider.get("/api/v1/session")).json()
    assert not session["features"]["voice"]
    response = await outsider.post("/api/v1/voice/transcriptions", content=audio(), headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())})
    assert response.status_code == 503 and not calls
