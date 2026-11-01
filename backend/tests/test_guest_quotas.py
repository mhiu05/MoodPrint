"""Durable shared trial quotas: lifetime counters, replay, rate, concurrency (GE-07.1)."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from tests.guest_helpers import add_guest

pytestmark = pytest.mark.postgres


async def claim(app, guest, kind="ai", key=None, digest="d" * 64, ms=0):
    from app.infrastructure.database.models import User
    from app.modules.guests.limits import reserve_guest_quota

    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, guest.user_id)
        return await reserve_guest_quota(
            db,
            user,
            kind=kind,
            operation_key=key or str(uuid4()),
            payload_digest=digest,
            settings=app.state.settings,
            voice_milliseconds=ms,
        )


async def finish(app, guest, kind, claimed):
    from app.modules.guests.limits import finish_guest_quota

    async with app.state.database.sessions.begin() as db:
        await finish_guest_quota(
            db, guest.user_id, kind, claimed.operation_key_hash, claimed.lease_token
        )


async def usage(app, guest):
    from app.modules.guests.models import GuestUsage

    async with app.state.database.sessions() as db:
        return await db.get(GuestUsage, guest.user_id)


def relax(app, **overrides):
    """Lift the rate/concurrency ceilings so one limit at a time can be proven."""
    values = {"guest_ai_per_minute": 1000, "guest_voice_per_minute": 1000, **overrides}
    for name, value in values.items():
        setattr(app.state.settings, name, value)


async def test_trial_quota_survives_rotation_restart_midnight(clients):
    from app.core.errors import DomainError

    app, _ = clients
    relax(app)
    guest = await add_guest(app)
    first = None
    for index in range(50):
        claimed = await claim(app, guest, key=f"turn-{index}")
        first = first or claimed
        await finish(app, guest, "ai", claimed)
    assert (await usage(app, guest)).ai_turns == 50
    with pytest.raises(DomainError) as exhausted:
        await claim(app, guest)
    assert exhausted.value.status == 429 and exhausted.value.code == "GUEST_QUOTA_EXHAUSTED"
    # The same client message id is a replay: same claim, no increment.
    again = await claim(app, guest, key="turn-0")
    assert again.operation_key_hash == first.operation_key_hash
    assert (await usage(app, guest)).ai_turns == 50
    # A new credential for the same trial (rotation) and a fresh calendar day change nothing: the
    # counter is a lifetime row keyed only by the user, never by session or by day.
    other_tab = await add_guest(app)
    assert (await usage(app, other_tab)).ai_turns == 0
    with pytest.raises(DomainError):
        await claim(app, guest, key="after-rotation")
    assert (await usage(app, guest)).ai_turns == 50


async def test_replay_with_different_payload_conflicts(clients):
    from app.core.errors import DomainError

    app, _ = clients
    relax(app)
    guest = await add_guest(app)
    await claim(app, guest, key="k", digest="a" * 64)
    with pytest.raises(DomainError) as conflict:
        await claim(app, guest, key="k", digest="b" * 64)
    assert conflict.value.status == 409 and conflict.value.code == "IDEMPOTENCY_CONFLICT"


async def test_voice_exact_milliseconds_and_concurrency(clients):
    from app.core.errors import DomainError

    app, _ = clients
    relax(app)
    guest = await add_guest(app)
    # 20 clips and exactly 600000 ms are allowed...
    for index in range(20):
        claimed = await claim(app, guest, "voice", f"clip-{index}", ms=30_000)
        await finish(app, guest, "voice", claimed)
    row = await usage(app, guest)
    assert (row.voice_clips, row.voice_milliseconds) == (20, 600_000)
    with pytest.raises(DomainError) as seventh:
        await claim(app, guest, "voice", "clip-20", ms=1)
    assert seventh.value.code == "GUEST_QUOTA_EXHAUSTED"

    # ...but a 30 second clip cannot fit after using 600 seconds.
    precise = await add_guest(app, usage={"voice_milliseconds": 599_999})
    with pytest.raises(DomainError):
        await claim(app, precise, "voice", "c", ms=2)

    # A processed clip is never redispatched or charged twice.
    done = await add_guest(app)
    dispatched = await claim(app, done, "voice", "same", ms=1000)
    from app.modules.guests.models import GuestOperationLink

    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestOperationLink)
            .where(GuestOperationLink.user_id == done.user_id)
            .values(state="completed")
        )
    with pytest.raises(DomainError) as replay:
        await claim(app, done, "voice", "same", ms=1000)
    assert replay.value.status == 409 and replay.value.code == "VOICE_ALREADY_PROCESSED"
    assert (await usage(app, done)).voice_clips == 1
    del dispatched


async def test_per_minute_and_per_guest_concurrency(clients):
    from app.core.errors import DomainError

    app, _ = clients
    guest = await add_guest(app)
    app.state.settings.guest_ai_per_minute = 2
    app.state.settings.guest_voice_per_minute = 2
    first = await claim(app, guest, "ai", "one")
    with pytest.raises(DomainError) as busy:
        await claim(app, guest, "ai", "two")  # 1 active per guest
    assert busy.value.code == "GUEST_BUSY" and busy.value.retry_after
    await finish(app, guest, "ai", first)
    second = await claim(app, guest, "ai", "two")
    await finish(app, guest, "ai", second)
    with pytest.raises(DomainError) as fast:
        await claim(app, guest, "ai", "three")  # 3rd within a minute
    assert fast.value.code == "GUEST_RATE_LIMITED" and fast.value.retry_after
    assert (await usage(app, guest)).ai_turns == 2, "a refused admission consumes nothing"


async def test_global_guest_ai_and_voice_ceilings_hold_under_contention(clients):
    from app.core.errors import DomainError

    app, _ = clients
    relax(app)
    guests = [await add_guest(app) for _ in range(14)]

    async def attempt(guest, kind):
        try:
            return await claim(app, guest, kind, str(uuid4()), ms=1000 if kind == "voice" else 0)
        except DomainError as error:
            return error.code

    ai = await asyncio.gather(*(attempt(guest, "ai") for guest in guests[:12]))
    assert sum(not isinstance(result, str) for result in ai) == 10
    assert ai.count("GUEST_CAPACITY") == 2
    voice = await asyncio.gather(*(attempt(guest, "voice") for guest in guests[:5]))
    assert sum(not isinstance(result, str) for result in voice) == 3
    assert voice.count("GUEST_CAPACITY") == 2


async def test_stale_claims_do_not_hold_capacity(clients):
    from app.modules.guests.models import GuestOperationLink

    app, _ = clients
    relax(app)
    guest = await add_guest(app)
    await claim(app, guest, "ai", "stuck")
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(GuestOperationLink).values(lease_until=GuestOperationLink.created_at - timedelta(seconds=1)))
    # The lease expired (e.g. a restart): the slot is free again and the turn is never replayed.
    again = await claim(app, guest, "ai", "fresh")
    assert again.operation_key_hash
    async with app.state.database.sessions() as db:
        states = (await db.scalars(select(GuestOperationLink.state))).all()
    assert states.count("claimed") == 2


async def test_session_quota_view_reflects_durable_counters(clients):
    from app.infrastructure.database.models import User
    from app.modules.guests.limits import guest_quota_view

    app, _ = clients
    relax(app)
    guest = await add_guest(app, usage={"ai_turns": 49, "voice_clips": 19, "voice_milliseconds": 599_999})
    async with app.state.database.sessions() as db:
        view = await guest_quota_view(db, await db.get(User, guest.user_id), app.state.settings)
    assert (view.ai_turns_remaining, view.voice_clips_remaining) == (1, 1)
    assert view.ai_turns_limit == 50
    assert view.voice_seconds_remaining == pytest.approx(0.001)
