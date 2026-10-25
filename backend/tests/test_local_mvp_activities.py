"""Each shipped activity retains the common authorization/concurrency contract."""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import now
from app.modules.activities.jobs import advance_due
from app.modules.activities.models import ActivitySession
from tests.activity_helpers import command, enable, invite, started
from tests.social_helpers import consent, key, open_room

pytestmark = pytest.mark.postgres
KINDS = ("icebreaker", "coop_quiz", "focus")


@pytest.mark.parametrize("kind", KINDS)
async def test_each_activity_serializes_invites_and_replays_duplicate_requests(clients, kind):
    app, actors, _, room = await open_room(clients)
    enable(app)
    a, b = actors[0][0], actors[1][0]
    headers = key()
    replies = await asyncio.gather(
        invite(a, room, kind, headers=headers),
        invite(a, room, kind, headers=headers),
        invite(b, room, kind),
    )
    assert replies[0].status_code == replies[1].status_code
    if replies[0].status_code == 201:
        assert replies[0].json()["id"] == replies[1].json()["id"]
    else:
        assert replies[0].status_code == 409
        assert replies[2].status_code == 201
    assert replies[2].status_code in (201, 409)
    async with app.state.database.sessions() as db:
        rows = (
            await db.scalars(
                select(ActivitySession).where(ActivitySession.connection_id == UUID(room))
            )
        ).all()
        assert len(rows) == 1


@pytest.mark.parametrize("kind", KINDS)
async def test_each_activity_refuses_expired_invitations(clients, kind):
    app, actors, _, room = await open_room(clients)
    enable(app)
    a, b = actors[0][0], actors[1][0]
    sent = (await invite(a, room, kind)).json()
    assert await advance_due(app, now() + timedelta(minutes=11)) == 1
    async with app.state.database.sessions() as db:
        row = await db.get(ActivitySession, UUID(sent["id"]))
        assert (row.state, row.end_reason) == ("expired", "invite_expired")
    expired = await command(b, sent["id"], "accept", sent["version"])
    assert expired.status_code in (409, 410)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("revoke", ["block", "end", "consent"])
async def test_each_activity_loses_access_on_each_room_revocation(clients, kind, revoke):
    app, actors, _, room = await open_room(clients)
    enable(app)
    a, b = actors[0][0], actors[1][0]
    active = await started(a, b, room, kind)
    stale = await command(a, active["id"], "end", active["version"] - 1)
    assert stale.status_code == 409
    from tests.conftest import add_actor

    outsider, _ = await add_actor(app, 99)
    await consent(outsider)
    assert (await outsider.get(f"/api/v1/activities/{active['id']}")).status_code == 404
    if revoke == "block":
        result = await b.post(f"/api/v1/connections/{room}/block", json={}, headers=key())
        assert result.status_code == 201
    elif revoke == "end":
        view = (await b.get(f"/api/v1/connections/{room}")).json()
        result = await b.post(
            f"/api/v1/connections/{room}/end",
            json={"expectedVersion": view["version"]},
            headers=key(),
        )
        assert result.status_code == 200
    else:
        await consent(b, enabled=False, expected=2)
    assert (await a.get(f"/api/v1/activities/{active['id']}")).status_code == 403
    assert (await command(a, active["id"], "end", active["version"])).status_code == 403
