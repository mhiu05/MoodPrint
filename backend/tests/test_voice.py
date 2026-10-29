import asyncio
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


def sample_audio(frames, rate):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_wav_sample_quantum_boundaries(rate, extra):
    from app.modules.guests.pricing import voice_upper
    from app.modules.voice.service import validate_audio
    from tests.test_guest_budget import PRICING

    duration = validate_audio(sample_audio(rate * 15 + extra, rate))
    assert duration == (rate * 15 + extra) / rate
    assert voice_upper(PRICING, duration) == ("synthetic-v1", 210 if extra == 1 else 105)


@pytest.mark.postgres
@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
@pytest.mark.parametrize("extra", [-1, 0, 1])
async def test_guest_voice_quota_rounds_fractional_sample_up(clients, rate, extra):
    from sqlalchemy import select

    from app.modules.guests.models import GuestCostReservation, GuestUsage
    from tests.guest_helpers import add_guest, enable_paid_fixture
    from tests.test_guest_paid_dispatch import CountingTranscriber

    app, _ = clients
    enable_paid_fixture(app)
    guest = await add_guest(app, consents=True)
    provider = CountingTranscriber()
    app.state.transcriber = provider
    key = str(uuid4())
    body = sample_audio(rate * 15 + extra, rate)
    headers = {"Content-Type": "audio/wav", "Idempotency-Key": key}
    response = await guest.client.post('/api/v1/voice/transcriptions', content=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['durationSeconds'] == (rate * 15 + extra) / rate
    async with app.state.database.sessions() as db:
        usage = await db.scalar(select(GuestUsage).where(GuestUsage.user_id == guest.user_id))
        assert usage.voice_milliseconds == (15001 if extra == 1 else 15000)
        assert usage.voice_clips == 1
        reservation = await db.scalar(select(GuestCostReservation))
        assert reservation.state == 'settled'
        assert reservation.upper_nano_usd == reservation.charged_nano_usd == (210 if extra == 1 else 105)
    replay = await guest.client.post('/api/v1/voice/transcriptions', content=body, headers=headers)
    assert replay.status_code == 409 and provider.calls == 1


@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
def test_wav_exact_thirty_second_limit(rate):
    from app.core.errors import DomainError
    from app.modules.voice.service import validate_audio

    assert validate_audio(sample_audio(rate * 30, rate)) == 30.0
    with pytest.raises(DomainError, match="INVALID_AUDIO"):
        validate_audio(sample_audio(rate * 30 + 1, rate))


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
async def test_voice_withdrawal_cancels_inflight_provider_call(clients):
    app, actors = clients
    a, _ = actors[0]
    for purpose in ("AI", "VOICE"):
        granted = await a.put(
            f"/api/v1/consents/{purpose}",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert granted.status_code == 200, granted.text
    started, cancelled = asyncio.Event(), asyncio.Event()

    class SlowTranscriber:
        async def transcribe(self, data):
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return "must not reach the user"

    app.state.transcriber = SlowTranscriber()
    from app.modules.voice import routes

    routes.VOICE_LIMIT.attempts.clear()
    routes.VOICE_DAILY_LIMIT.attempts.clear()
    upload = asyncio.create_task(a.post(
        "/api/v1/voice/transcriptions", content=audio(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    ))
    # Provider entry waits on consent transactions. The cancellation window below
    # stays short; this budget only covers a busy disposable database.
    started_task = asyncio.create_task(started.wait())
    done, _pending = await asyncio.wait(
        {upload, started_task}, timeout=15, return_when=asyncio.FIRST_COMPLETED
    )
    if not started.is_set():
        if upload in done:
            failure = upload.exception()
            if failure is not None:
                raise AssertionError("voice request failed before the provider") from failure
            response = upload.result()
            raise AssertionError(
                f"provider was not called: {response.status_code} {response.text}"
            )
        raise AssertionError("provider did not start within 15s")
    started_task.cancel()
    withdrawn = await a.put(
        "/api/v1/consents/VOICE",
        json={"enabled": False, "expectedVersion": 2, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    response = await asyncio.wait_for(upload, timeout=3)
    assert response.status_code in (403, 409)
    assert cancelled.is_set()


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


@pytest.mark.postgres
async def test_voice_uploads_are_rate_limited_before_reaching_the_paid_provider(clients):
    from app.modules.voice import routes

    routes.VOICE_LIMIT.attempts.clear()
    routes.VOICE_DAILY_LIMIT.attempts.clear()
    app, actors = clients
    a, _ = actors[0]
    for purpose in ("AI", "VOICE"):
        await a.put(
            f"/api/v1/consents/{purpose}",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
            headers={"Idempotency-Key": str(uuid4())},
        )
    calls = []

    class CountingTranscriber:
        async def transcribe(self, data):
            calls.append(len(data))
            return "Bản chữ"

    app.state.transcriber = CountingTranscriber()
    statuses = []
    for _ in range(routes.VOICE_LIMIT.limit + 2):
        response = await a.post(
            "/api/v1/voice/transcriptions",
            content=audio(),
            headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
        )
        statuses.append(response.status_code)
    assert statuses.count(200) == routes.VOICE_LIMIT.limit
    assert statuses[-1] == 429
    assert len(calls) == routes.VOICE_LIMIT.limit
    assert routes.VOICE_SLOTS.active == {}
