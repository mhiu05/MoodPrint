"""T-ACT-02/05: activity lifecycle API, races, idempotency, authorization and limits."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.infrastructure.database.models import now
from app.modules.activities.models import ActivitySession
from app.modules.social.models import Connection
from tests.activity_helpers import command, current, enable, invite, started
from tests.conftest import add_actor
from tests.social_helpers import consent, key, open_room

pytestmark = pytest.mark.postgres


async def activity_seq(app, room):
    async with app.state.database.sessions() as db:
        return await db.scalar(select(Connection.activity_seq).where(Connection.id == UUID(room)))


async def test_catalog_and_flags(clients):
    app, actors, _, room = await open_room(clients)
    a = actors[0][0]
    assert (await a.get("/api/v1/activities/catalog")).json() == []
    response = await invite(a, room)
    assert response.status_code == 503 and response.json()["error"]["code"] == "ACTIVITIES_DISABLED"
    enable(app, ("icebreaker",))
    catalog = (await a.get("/api/v1/activities/catalog")).json()
    assert [item["kind"] for item in catalog] == ["icebreaker"]
    assert catalog[0]["estimatedMinutes"] == 5 and catalog[0]["rounds"] == 3
    assert (await invite(a, room, "focus")).status_code == 422
    enable(app)
    focus_card = next(
        i for i in (await a.get("/api/v1/activities/catalog")).json() if i["kind"] == "focus"
    )
    assert focus_card["focusPlans"] == [[25, 5], [15, 3], [50, 10]] and focus_card["maxCycles"] == 4


async def test_invite_is_visible_to_both_and_bumps_the_watermark(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    before = await activity_seq(app, room)
    sent = await invite(a, room)
    assert sent.status_code == 201, sent.text
    mine = sent.json()
    assert (mine["state"], mine["role"], mine["kind"]) == ("invited", "inviter", "icebreaker")
    assert mine["expiresAt"] and mine["serverTime"] and mine["current"] is None
    theirs = await current(b, room)
    assert (theirs["id"], theirs["role"], theirs["self"]["accepted"]) == (
        mine["id"],
        "invitee",
        False,
    )
    assert await activity_seq(app, room) == before + 1
    rows = (await b.get("/api/v1/connections")).json()
    assert rows[0]["activeActivity"] == "icebreaker"
    assert (await b.get("/api/v1/social/summary")).json()["activityInvites"] == 1
    assert (await a.get("/api/v1/social/summary")).json()["activityInvites"] == 0


async def test_concurrent_invites_from_both_sides_create_exactly_one_session(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    first, second = await asyncio.gather(invite(a, room), invite(b, room, "coop_quiz"))
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409], (first.text, second.text)
    created = first if first.status_code == 201 else second
    refused = second if created is first else first
    assert refused.json()["error"]["code"] == "ACTIVITY_IN_PROGRESS"
    assert refused.json()["error"]["currentSessionId"] == created.json()["id"]
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ActivitySession)) == 1


async def test_accept_and_cancel_race_has_exactly_one_outcome(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    accept, cancel = await asyncio.gather(
        command(b, session["id"], "accept", session["version"]),
        command(a, session["id"], "cancel", session["version"]),
    )
    assert sorted([accept.status_code, cancel.status_code]) == [200, 409]
    winner = accept if accept.status_code == 200 else cancel
    async with app.state.database.sessions() as db:
        state = await db.scalar(select(ActivitySession.state))
    assert state == winner.json()["state"] and state in ("active", "cancelled")


async def test_replay_returns_the_same_view_and_stale_versions_are_refused(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    headers = key()
    first = await command(b, session["id"], "accept", session["version"], headers)
    replay = await command(b, session["id"], "accept", session["version"], headers)
    assert first.status_code == replay.status_code == 200
    strip = lambda body: {k: v for k, v in body.items() if k != "serverTime"}  # noqa: E731
    assert strip(first.json()) == strip(replay.json())
    stale = await command(a, session["id"], "end", session["version"])
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "ACTIVITY_CHANGED"
    ended = await command(a, session["id"], "end", first.json()["version"])
    assert ended.status_code == 200 and ended.json()["endReason"] == "ended_by_self"
    peer_view = await current(b, room)
    assert peer_view["endReason"] == "ended_by_peer"


async def test_only_the_two_members_of_a_live_room_can_read_or_act(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    c, _ = await add_actor(app, 3)
    await consent(c)
    for path in (
        f"/api/v1/activities/{session['id']}",
        f"/api/v1/connections/{room}/activities/current",
    ):
        assert (await c.get(path)).status_code == 404
    assert (await command(c, session["id"], "accept", 1)).status_code == 404
    assert (await command(a, session["id"], "accept", 1)).status_code == 403  # inviter
    assert (await command(b, uuid4(), "accept", 1)).status_code == 404
    view = (await a.get(f"/api/v1/connections/{room}")).json()
    await a.post(
        f"/api/v1/connections/{room}/end", json={"expectedVersion": view["version"]}, headers=key()
    )
    assert (await b.get(f"/api/v1/activities/{session['id']}")).status_code == 403
    assert (await invite(b, room)).status_code == 403


async def test_invites_per_connection_hour_are_limited(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    a = actors[0][0]
    for _ in range(6):
        session = (await invite(a, room)).json()
        assert (await command(a, session["id"], "cancel", session["version"])).status_code == 200
    limited = await invite(a, room)
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "ACTIVITY_INVITE_QUOTA"
    assert int(limited.headers["Retry-After"]) > 0


async def test_invites_per_user_day_are_limited(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, a_id), (_, b_id) = actors
    async with app.state.database.sessions.begin() as db:
        connection = await db.get(Connection, UUID(room))
        for hours in range(20):
            db.add(
                ActivitySession(
                    connection_id=connection.id,
                    pair_id=connection.pair_id,
                    kind="icebreaker",
                    definition_version="icebreaker-v1",
                    inviter_id=a_id,
                    invitee_id=b_id,
                    state="cancelled",
                    created_at=now() - timedelta(hours=1, minutes=hours),
                )
            )
    limited = await invite(a, room)
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "ACTIVITY_INVITE_QUOTA"


async def test_decline_starts_a_ten_minute_cooldown_for_that_kind(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    session = (await invite(a, room)).json()
    assert (await command(b, session["id"], "decline", session["version"])).status_code == 200
    assert (await current(a, room))["endReason"] == "invite_declined"
    again = await invite(a, room)
    assert again.status_code == 429 and again.json()["error"]["code"] == "ACTIVITY_COOLDOWN"
    assert 0 < int(again.headers["Retry-After"]) <= 601
    assert (await invite(a, room, "coop_quiz")).status_code == 201
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(ActivitySession)
            .where(ActivitySession.kind == "icebreaker")
            .values(ended_at=now() - timedelta(minutes=11))
        )


async def test_every_mutation_bumps_the_room_watermark(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    start = await activity_seq(app, room)
    view = await started(a, b, room)
    assert await activity_seq(app, room) == start + 2
    await command(a, view["id"], "end", view["version"])
    assert await activity_seq(app, room) == start + 3
