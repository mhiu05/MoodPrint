"""T-ACT-03 (backend), T-ACT-04, T-PRIV-01: events, aborts, retention, export, deletion."""

import asyncio
import json
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update
from starlette.requests import Request

from app.core.security import Actor
from app.infrastructure.database.models import AuthSession, now
from app.modules.activities.models import ActivityParticipant, ActivityResponse, ActivitySession
from tests.activity_helpers import enable, invite, ready, respond, started
from tests.social_helpers import consent, key, open_room

pytestmark = pytest.mark.postgres


async def stream(app, uid, room):
    from app.modules.social.notifications import event_stream

    async with app.state.database.sessions() as db:
        own = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": app,
            "query_string": b"",
        }
    )
    return event_stream(request, Actor(uid, own.id, 1), UUID(room), after_seq=0)


def envelope(chunk):
    return json.loads(next(line[6:] for line in chunk.splitlines() if line.startswith("data: ")))


async def test_stream_announces_activity_changes_separately_from_messages(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, b_id) = actors
    events = await stream(app, b_id, room)
    assert "messages_available" in await anext(events)
    await invite(a, room)
    chunk = await asyncio.wait_for(anext(events), 3)
    assert "event: activity_changed" in chunk
    data = envelope(chunk)
    assert data["version"] == "social-events-v2" and data["activitySeq"] == 1
    assert data["eventId"] == f"{room}:a1" and "text" not in data
    sent = await a.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "chào", "clientMessageId": "00000000-0000-4000-8000-000000000001"},
        headers=key(),
    )
    assert sent.status_code == 201
    chunk = await asyncio.wait_for(anext(events), 3)
    assert "event: messages_available" in chunk and "activity_changed" not in chunk
    await a.post(f"/api/v1/connections/{room}/block", json={}, headers=key())
    assert "access_revoked" in await asyncio.wait_for(anext(events), 3)
    await events.aclose()


async def active_session(clients):
    app, actors, refs, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    view = await started(a, b, room)
    await respond(a, view["id"], 1, text="CÂU-TRẢ-LỜI-CỦA-A")
    return app, actors, refs, room, view["id"]


async def session_row(app, sid):
    async with app.state.database.sessions() as db:
        return await db.get(ActivitySession, UUID(sid))


async def test_block_aborts_and_denies_the_session(clients):
    app, actors, _, room, sid = await active_session(clients)
    (a, _), (b, _) = actors
    assert (
        await b.post(f"/api/v1/connections/{room}/block", json={}, headers=key())
    ).status_code == 201
    row = await session_row(app, sid)
    assert (row.state, row.end_reason) == ("aborted", "blocked")
    assert (await a.get(f"/api/v1/activities/{sid}")).status_code == 403


async def test_ending_the_connection_aborts_with_room_closed(clients):
    app, actors, _, room, sid = await active_session(clients)
    (a, _), (b, _) = actors
    view = (await a.get(f"/api/v1/connections/{room}")).json()
    await a.post(
        f"/api/v1/connections/{room}/end", json={"expectedVersion": view["version"]}, headers=key()
    )
    row = await session_row(app, sid)
    assert (row.state, row.end_reason) == ("aborted", "room_closed")
    assert (await b.get(f"/api/v1/connections/{room}/activities/current")).status_code == 403


async def test_match_withdrawal_aborts_with_consent_withdrawn(clients):
    app, actors, _, room, sid = await active_session(clients)
    (a, _), (b, _) = actors
    await consent(b, enabled=False, expected=2)
    row = await session_row(app, sid)
    assert (row.state, row.end_reason) == ("aborted", "consent_withdrawn")
    assert (await a.get(f"/api/v1/activities/{sid}")).status_code == 403


async def test_account_deletion_aborts_and_removes_own_answers(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors, _, room, sid = await active_session(clients)
    (a, a_id), (b, _) = actors
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    deletion = await a.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": version},
        headers=key(),
    )
    assert deletion.status_code == 202, deletion.text
    assert (await b.get(f"/api/v1/activities/{sid}")).status_code == 403
    await process_deletions(app)
    row = await session_row(app, sid)
    assert (row.state, row.end_reason) == ("aborted", "account_deleted")
    async with app.state.database.sessions() as db:
        assert (
            await db.scalars(select(ActivityResponse).where(ActivityResponse.user_id == a_id))
        ).all() == []


async def test_retention_purges_old_answers_and_old_finished_sessions_only(clients):
    from app.jobs.retention import purge_expired

    app, actors, _, room, sid = await active_session(clients)
    (a, a_id), (b, b_id) = actors
    view = (await a.get(f"/api/v1/activities/{sid}")).json()
    await a.post(
        f"/api/v1/activities/{sid}/end", json={"expectedVersion": view["version"]}, headers=key()
    )
    recent = (await invite(a, room)).json()["id"]
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(ActivityResponse).values(submitted_at=now() - timedelta(days=91)))
        await db.execute(
            update(ActivitySession)
            .where(ActivitySession.id == UUID(sid))
            .values(ended_at=now() - timedelta(days=91))
        )
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(ActivityResponse))).all() == []
        assert [str(i) for i in (await db.scalars(select(ActivitySession.id))).all()] == [recent]
        assert (
            await db.scalars(
                select(ActivityParticipant).where(ActivityParticipant.session_id == UUID(sid))
            )
        ).all() == []


async def test_export_has_own_activity_data_and_never_the_peer_answers(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    sid = (await started(a, b, room))["id"]
    await respond(a, sid, 1, text="CỦA-A")
    await respond(b, sid, 1, text="CỦA-B")
    await ready(a, sid, 1)
    job = (await a.post("/api/v1/exports", json={"scopes": ["social"]}, headers=key())).json()
    exported = (await a.get(f"/api/v1/exports/{job['id']}/download")).json()["social"]
    sessions = exported["activities"]["sessions"]
    assert sessions[0]["kind"] == "icebreaker" and sessions[0]["role"] == "inviter"
    assert [r["text"] for r in exported["activities"]["responses"]] == ["CỦA-A"]
    assert "CỦA-B" not in json.dumps(exported, ensure_ascii=False)
