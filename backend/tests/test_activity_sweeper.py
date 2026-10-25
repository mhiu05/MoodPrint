"""D-06: the deadline sweeper expires invites and races safely with user actions."""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import now
from app.modules.activities.jobs import advance_due
from app.modules.activities.models import ActivitySession
from app.modules.social.models import Connection
from tests.activity_helpers import command, current, enable, invite
from tests.social_helpers import open_room

pytestmark = pytest.mark.postgres


async def test_old_invites_expire_and_bump_the_watermark(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    assert await advance_due(app, now() + timedelta(minutes=9)) == 0
    async with app.state.database.sessions() as db:
        before = await db.scalar(select(Connection.activity_seq).where(Connection.id == UUID(room)))
    assert await advance_due(app, now() + timedelta(minutes=11)) == 1
    view = await current(b, room)
    assert (view["state"], view["endReason"]) == ("expired", "invite_expired")
    async with app.state.database.sessions() as db:
        after = await db.scalar(select(Connection.activity_seq).where(Connection.id == UUID(room)))
    assert after == before + 1
    late = await command(b, session["id"], "accept", session["version"])
    assert late.status_code == 409


async def test_accept_and_sweep_racing_have_one_consistent_outcome(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    async with app.state.database.sessions.begin() as db:
        row = await db.get(ActivitySession, UUID(session["id"]))
        row.deadline_at = now() - timedelta(seconds=1)  # due now, still accept-able by the route
    accept, swept = await asyncio.gather(
        command(b, session["id"], "accept", session["version"]),
        advance_due(app, now() + timedelta(minutes=11)),
    )
    state = (await current(b, room))["state"]
    if accept.status_code == 200:
        assert state == "active" and swept == 0
    else:
        assert accept.status_code == 409 and state == "expired" and swept == 1


async def test_a_locked_room_is_skipped_and_handled_on_the_next_tick(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    a = actors[0][0]
    await invite(a, room)
    later = now() + timedelta(minutes=11)
    async with app.state.database.sessions() as db, db.begin():
        await db.scalar(select(Connection).where(Connection.id == UUID(room)).with_for_update())
        assert await advance_due(app, later) == 0
    assert await advance_due(app, later) == 1
