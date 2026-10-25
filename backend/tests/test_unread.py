"""DR-13: private read markers drive unread counts and the social summary; no receipts."""

from uuid import uuid4

import pytest

from tests.conftest import add_actor
from tests.social_helpers import consent, key, open_room, published_pair

pytestmark = pytest.mark.postgres


async def say(client, room, text):
    response = await client.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": text, "clientMessageId": str(uuid4())},
        headers=key(),
    )
    assert response.status_code == 201, response.text


async def read(client, room, seq):
    return await client.post(
        f"/api/v1/connections/{room}/read", json={"seq": str(seq)}, headers=key()
    )


async def row(client, room):
    rows = (await client.get("/api/v1/connections")).json()
    return next(item for item in rows if item["id"] == room)


async def test_unread_count_is_monotonic_and_ignores_out_of_order_reads(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    for text in ("một", "hai", "ba " + "x" * 120):
        await say(a, room, text)
    view = await row(b, room)
    assert view["unreadCount"] == 3
    assert view["lastMessagePreview"] == ("ba " + "x" * 120)[:80]
    assert view["lastMessageSender"] == "peer" and view["lastMessageAt"]
    assert (await row(a, room))["unreadCount"] == 0  # own messages never count
    assert (await row(a, room))["lastMessageSender"] == "self"
    response = await read(b, room, 2)
    assert response.status_code == 200 and response.json() == {"lastReadSeq": "2"}
    assert (await row(b, room))["unreadCount"] == 1
    response = await read(b, room, 1)
    assert response.json() == {"lastReadSeq": "2"}  # never moves backwards
    assert (await row(b, room))["unreadCount"] == 1
    response = await read(b, room, 99)
    assert response.json() == {"lastReadSeq": "3"}  # clamped to the room's high water
    assert (await row(b, room))["unreadCount"] == 0
    assert (await read(b, room, "x")).status_code == 422


async def test_summary_counts_incoming_requests_and_unread_connections(clients):
    app, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await say(a, room, "chào")
    summary = (await b.get("/api/v1/social/summary")).json()
    assert summary == {"pendingIncomingRequests": 0, "unreadConnections": 1, "activityInvites": 0}
    assert (await a.get("/api/v1/social/summary")).json()["unreadConnections"] == 0
    await consent(b, enabled=False, expected=2)
    response = await b.get("/api/v1/social/summary")
    assert response.status_code == 200
    assert response.json() == {
        "pendingIncomingRequests": 0,
        "unreadConnections": 0,
        "activityInvites": 0,
    }


async def test_summary_counts_pending_incoming_requests(clients):
    _, actors, refs = await published_pair(clients)
    (a, _), (b, _) = actors
    await a.post("/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key())
    assert (await b.get("/api/v1/social/summary")).json()["pendingIncomingRequests"] == 1
    assert (await a.get("/api/v1/social/summary")).json()["pendingIncomingRequests"] == 0


async def test_third_user_cannot_mark_a_pair_room_read(clients):
    app, actors, _, room = await open_room(clients)
    c, _ = await add_actor(app, 2)
    await consent(c)
    response = await read(c, room, 1)
    assert response.status_code in (403, 404)
    response = await c.post(f"/api/v1/connections/{uuid4()}/read", json={"seq": "1"}, headers=key())
    assert response.status_code == 404
