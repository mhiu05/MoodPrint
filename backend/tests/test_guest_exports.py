"""Guest exports, account deletion and voice honour the trial lifetime without passwords (GE-05.4)."""

import asyncio
import io
import wave
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.infrastructure.database.models import AuthSession
from tests.guest_helpers import add_guest, db_now, enable_paid_fixture

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)
CONFIRM = "guest-data-v1"


async def test_quota_heartbeat_reports_trial_expiry_instead_of_generic_fence(clients):
    from app.core.errors import DomainError
    from app.modules.guests.limits import maintain_guest_quota
    from tests.test_guest_quotas import claim

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME-timedelta(seconds=2))
    ticket = await claim(app, guest)
    async def held():
        async with maintain_guest_quota(app.state.database, guest.user_id, "ai", ticket):
            await asyncio.Event().wait()
    with pytest.raises(DomainError, match="GUEST_EXPIRED"):
        await asyncio.wait_for(held(), 5)


def headers():
    return {"Idempotency-Key": str(uuid4())}


async def add_item(guest, text="Điều riêng tư PRIVATE-CANARY"):
    created = await guest.client.post(
        "/api/v1/profiles/private-items", json={"text": text}, headers=headers()
    )
    assert created.status_code == 201, created.text


async def test_guest_export_cannot_download_at_t(clients):
    import time

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=4))
    await add_item(guest)
    created = await guest.client.post(
        "/api/v1/exports",
        json={"scopes": ["private_items"], "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    assert created.status_code == 201, created.text
    job = created.json()["id"]
    stored = app.state.exports[__import__("uuid").UUID(job)]
    assert stored["expires"] - time.monotonic() <= 4.5, "RAM TTL is min(900s, remaining trial)"

    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.3)
    late = await guest.client.get(f"/api/v1/exports/{job}/download")
    assert late.status_code == 401 and late.json()["error"]["code"] == "GUEST_EXPIRED"
    assert b"PRIVATE-CANARY" not in late.content


async def test_guest_export_needs_confirmation_and_never_includes_social(clients):
    app, _ = clients
    guest = await add_guest(app)
    await add_item(guest)
    missing = await guest.client.post(
        "/api/v1/exports", json={"scopes": ["private_items"]}, headers=headers()
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "GUEST_CONFIRMATION_REQUIRED"
    social = await guest.client.post(
        "/api/v1/exports",
        json={"scopes": ["private_items", "social"], "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    assert social.status_code == 403 and social.json()["error"]["code"] == "REGISTERED_REQUIRED"
    ok = await guest.client.post(
        "/api/v1/exports",
        json={"scopes": ["private_items", "consents"], "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    assert ok.status_code == 201, "no password step-up for a guest"
    download = await guest.client.get(f"/api/v1/exports/{ok.json()['id']}/download")
    assert download.status_code == 200 and "PRIVATE-CANARY" in download.text
    assert (
        await guest.client.get(f"/api/v1/exports/{ok.json()['id']}/download")
    ).status_code == 410, "a second download is gone"
    # Another trial can neither see nor fetch it.
    other = await add_guest(app)
    assert (
        await other.client.get(f"/api/v1/exports/{ok.json()['id']}/download")
    ).status_code == 404


async def test_export_reauth_registered_only(clients):
    app, actors = clients
    registered, registered_id = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == registered_id)
            .values(reauthenticated_at=datetime(1970, 1, 1, tzinfo=UTC))
        )
    denied = await registered.post(
        "/api/v1/exports",
        json={"scopes": ["private_items"], "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    # A guest confirmation is ignored for a registered account: step-up is still required.
    assert denied.status_code == 401 and denied.json()["error"]["code"] == "REAUTH_REQUIRED"
    deletion = await registered.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": 1, "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    assert deletion.status_code == 401 and deletion.json()["error"]["code"] == "REAUTH_REQUIRED"


async def test_guest_account_delete_uses_hard_purge_queue(clients):
    from app.infrastructure.database.models import AuthSession, User
    from app.modules.guests.models import GuestCleanupJob
    from app.modules.users.models import DataJob

    app, _ = clients
    guest = await add_guest(app)
    unconfirmed = await guest.client.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": 1},
        headers=headers(),
    )
    assert unconfirmed.status_code == 422
    deleted = await guest.client.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": 1, "guestConfirmation": CONFIRM},
        headers=headers(),
    )
    assert deleted.status_code == 204 and deleted.content == b""
    async with app.state.database.sessions() as db:
        user = await db.get(User, guest.user_id)
        job = await db.get(GuestCleanupJob, guest.user_id)
        sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))).all()
        legacy_jobs = await db.scalar(select(func.count()).select_from(DataJob))
        now = await db_now(app)
    assert user.status == "deleting" and all(s.revoked for s in sessions)
    assert job.due_at <= now and legacy_jobs == 0, "hard purge queue, not the registered tombstone worker"
    assert (await guest.client.get("/api/v1/session")).status_code == 401


def wav_bytes(seconds=0.2, rate=8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


class SlowTranscriber:
    def __init__(self):
        self.calls, self.started, self.release = 0, asyncio.Event(), asyncio.Event()

    async def transcribe(self, data: bytes) -> str:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return "PRIVATE-TRANSCRIPT-CANARY"


async def test_voice_upload_and_result_crossing_t(clients):
    app, _ = clients
    transcriber = SlowTranscriber()
    app.state.transcriber = transcriber
    enable_paid_fixture(app)
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=4), consents=True)
    pending = asyncio.create_task(
        guest.client.post(
            "/api/v1/voice/transcriptions",
            content=wav_bytes(),
            headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
        )
    )
    await asyncio.wait_for(transcriber.started.wait(), 5)
    dispatched_before_t = transcriber.calls
    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.3)
    transcriber.release.set()  # the provider answers only after T
    response = await asyncio.wait_for(pending, 8)
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert "PRIVATE-TRANSCRIPT-CANARY" not in response.text
    assert dispatched_before_t == 1

    # After T nothing can start: no further provider dispatch.
    again = await guest.client.post(
        "/api/v1/voice/transcriptions",
        content=wav_bytes(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert again.status_code == 401 and transcriber.calls == 1


async def test_voice_audio_is_not_dispatched_when_the_deadline_passes_during_upload(clients):
    app, _ = clients
    transcriber = SlowTranscriber()
    app.state.transcriber = transcriber
    enable_paid_fixture(app)
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=2), consents=True)

    async def slow_body():
        yield wav_bytes()[:40]
        await asyncio.sleep(2.6)  # the visitor's upload stalls across T
        yield wav_bytes()[40:]

    response = await guest.client.post(
        "/api/v1/voice/transcriptions",
        content=slow_body(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 401
    assert transcriber.calls == 0, "no provider dispatch for audio that finished after T"
