"""DR-03: profile edits change discovery, never consent; rooms and requests survive them.

MATCH withdrawal, block, end and deletion still close rooms (covered here and in
test_social.py / test_privacy_lifecycle.py).
"""

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.core.security import Actor
from app.infrastructure.database.models import AuthSession
from tests.social_helpers import (
    PROFILE,
    consent,
    key,
    open_room,
    published_pair,
    republish,
    withdraw,
)

pytestmark = pytest.mark.postgres

EDITED = {**PROFILE, "interests": ["reading", "music", "cooking"], "style": "direct"}


async def say(client, room, text="xin chào"):
    return await client.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": text, "clientMessageId": str(uuid4())},
        headers=key(),
    )


async def stream_for(app, uid, room):
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


async def test_republish_keeps_room_messages_and_stream(clients, monkeypatch):
    from app.modules.social import notifications

    monkeypatch.setattr(notifications, "FULL_CHECK_SECONDS", 0)
    app, actors, _, room = await open_room(clients)
    (a, _), (b, b_id) = actors
    generator = await stream_for(app, b_id, room)
    assert "messages_available" in await anext(generator)
    await republish(a, EDITED)
    for client in (a, b):
        assert (await say(client, room)).status_code == 201
        page = await client.get(f"/api/v1/connections/{room}/messages")
        assert page.status_code == 200
    following = await anext(generator)
    assert "access_revoked" not in following and "messages_available" in following
    await generator.aclose()


async def test_withdrawn_profile_keeps_room_but_leaves_discovery(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await withdraw(a)
    assert (await say(a, room)).status_code == 201
    assert (await say(b, room)).status_code == 201
    assert [row["id"] for row in (await b.get("/api/v1/connections")).json()] == [room]
    assert (await b.get("/api/v1/matching/candidates")).json()["candidates"] == []


async def pending_request(clients):
    app, actors, refs = await published_pair(clients)
    response = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert response.status_code == 201, response.text
    incoming = next(
        row
        for row in (await actors[1][0].get("/api/v1/connection-requests")).json()
        if row["direction"] == "incoming"
    )
    return app, actors, incoming


async def test_pending_request_survives_compatible_republish(clients):
    _, actors, incoming = await pending_request(clients)
    await republish(actors[0][0], EDITED)
    response = await actors[1][0].post(
        f"/api/v1/connection-requests/{incoming['id']}/accept",
        json={"expectedVersion": incoming["version"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted" and response.json()["connectionId"]


async def test_withdrawn_sender_request_cannot_be_accepted_but_can_be_declined(clients):
    _, actors, incoming = await pending_request(clients)
    await withdraw(actors[0][0])
    body = {"expectedVersion": incoming["version"]}
    accept = await actors[1][0].post(
        f"/api/v1/connection-requests/{incoming['id']}/accept", json=body, headers=key()
    )
    assert accept.status_code == 409 and accept.json()["error"]["code"] == "REQUEST_CHANGED"
    decline = await actors[1][0].post(
        f"/api/v1/connection-requests/{incoming['id']}/decline", json=body, headers=key()
    )
    assert decline.status_code == 200, decline.text
    assert decline.json()["status"] == "declined"


async def test_match_withdrawal_still_closes_the_room(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await consent(b, enabled=False, expected=2)
    assert (await a.get(f"/api/v1/connections/{room}/messages")).status_code == 403
    assert (await say(a, room)).status_code == 403
    assert (await a.get("/api/v1/connections")).json() == []


async def test_connected_peer_who_republished_stays_out_of_discovery(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await republish(a, EDITED)
    for client in (a, b):
        assert (await client.get("/api/v1/matching/candidates")).json()["candidates"] == []
    assert [row["id"] for row in (await a.get("/api/v1/connections")).json()] == [room]


async def test_reveal_grant_works_after_republish(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await a.patch(
        "/api/v1/users/me/identity",
        json={"field": "displayName", "value": "Tên của A", "expectedVersion": 0},
        headers=key(),
    )
    await republish(a, EDITED)
    request = await b.post(
        f"/api/v1/connections/{room}/reveal-requests",
        json={"field": "displayName", "ownerSide": "peer", "expectedIdentityVersion": 1},
        headers=key(),
    )
    assert request.status_code == 201, request.text
    own = (await a.get(f"/api/v1/connections/{room}/reveal-requests")).json()[0]
    granted = await a.post(
        f"/api/v1/reveal-requests/{own['id']}/grant",
        json={"expectedVersion": own["version"], "previewDigest": own["previewDigest"]},
        headers=key(),
    )
    assert granted.status_code == 200, granted.text
    value = await b.get(f"/api/v1/reveal-grants/{own['id']}/value")
    assert value.status_code == 200 and json.loads(value.text)["value"] == "Tên của A"
