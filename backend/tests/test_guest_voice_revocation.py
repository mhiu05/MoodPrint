"""Withdrawal committed before the final send decision prevents audio disclosure."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.guest_helpers import add_guest, enable_paid_fixture
from tests.test_guest_paid_dispatch import CountingTranscriber, ledger, wav

pytestmark = pytest.mark.postgres


async def speaker(clients, kind):
    app, actors = clients
    enable_paid_fixture(app)
    if kind == "guest":
        client = (await add_guest(app, consents=True)).client
        version = 1
    else:
        client = actors[0][0]
        for purpose in ("AI", "VOICE"):
            result = await client.put(
                f"/api/v1/consents/{purpose}",
                json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert result.status_code == 200, result.text
        version = 2
    provider = CountingTranscriber()
    app.state.transcriber = provider
    return app, client, provider, version


async def withdraw(client, purpose, version):
    result = await client.put(
        f"/api/v1/consents/{purpose}",
        json={"enabled": False, "expectedVersion": version, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 200, result.text


async def assert_no_dispatch(app, provider, response):
    from app.modules.guests.models import GuestOperationLink
    from app.modules.voice.routes import VOICE_SLOTS

    assert response.status_code in (403, 409), response.text
    assert provider.calls == 0, "withdrawn audio reached the provider"
    assert "bản chữ" not in response.text
    days, reservations, _ = await ledger(app)
    assert all(row.dispatched_at is None for row in reservations)
    assert all(day.reserved_nano_usd == day.spent_nano_usd == 0 for day in days)
    async with app.state.database.sessions() as db:
        links = (await db.scalars(select(GuestOperationLink))).all()
        assert all(row.state not in ("claimed", "dispatched") for row in links)
    assert VOICE_SLOTS.active == {}


@pytest.mark.parametrize("kind", ["guest", "registered"])
@pytest.mark.parametrize("purpose", ["VOICE", "AI"])
async def test_upload_revocation_blocks_transcription(clients, monkeypatch, kind, purpose):
    from starlette.requests import Request

    from app.modules.voice import routes

    app, client, provider, version = await speaker(clients, kind)
    reached, resume = asyncio.Event(), asyncio.Event()
    authorized = False
    original_reserve, original_stream = routes.VOICE_SLOTS.reserve, Request.stream

    def reserve(*args, **kwargs):
        nonlocal authorized
        release = original_reserve(*args, **kwargs)
        authorized = True  # The route already checked consent, before reading its upload.
        return release

    async def stream(request):
        # Body-limit middleware buffers first. Intercept the route's stream only,
        # after its real initial authorization, not the earlier middleware read.
        if authorized and request.url.path.endswith('/voice/transcriptions'):
            reached.set()
            await resume.wait()
        async for chunk in original_stream(request):
            yield chunk

    monkeypatch.setattr(routes.VOICE_SLOTS, 'reserve', reserve)
    monkeypatch.setattr(Request, 'stream', stream)
    pending = asyncio.create_task(client.post(
        "/api/v1/voice/transcriptions", content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    ))
    try:
        await asyncio.wait_for(reached.wait(), 5)
        await withdraw(client, purpose, version)
    finally:
        resume.set()
    await assert_no_dispatch(app, provider, await asyncio.wait_for(pending, 5))


@pytest.mark.parametrize("kind", ["guest", "registered"])
@pytest.mark.parametrize("purpose", ["VOICE", "AI"])
async def test_revocation_during_dispatch_wait_blocks_transcription(clients, monkeypatch, kind, purpose):
    from app.modules.voice import routes

    app, client, provider, version = await speaker(clients, kind)
    reached, resume = asyncio.Event(), asyncio.Event()
    original = routes.guard_guest_dispatch

    async def wait_at_dispatch(*args, **kwargs):
        result = await original(*args, **kwargs)
        reached.set()
        await resume.wait()
        return result

    monkeypatch.setattr(routes, "guard_guest_dispatch", wait_at_dispatch)
    pending = asyncio.create_task(client.post(
        "/api/v1/voice/transcriptions", content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    ))
    try:
        await asyncio.wait_for(reached.wait(), 5)
        await withdraw(client, purpose, version)
    finally:
        resume.set()
    await assert_no_dispatch(app, provider, await asyncio.wait_for(pending, 5))


@pytest.mark.parametrize("kind", ["guest", "registered"])
async def test_permitted_voice_dispatch_calls_provider_once(clients, kind):
    _, client, provider, _ = await speaker(clients, kind)
    response = await client.post(
        "/api/v1/voice/transcriptions", content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    assert provider.calls == 1
