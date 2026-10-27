"""Real PostgreSQL tests for export scope, deletion lifecycle and cross-user isolation.

Breaks caught: peer text or report evidence leaking into an export, exports
readable from another account or session, oversize exports crashing, mood
deletion touching unrelated data, account deletion leaving rooms live or the
old session usable, guessed room IDs, foreign room writes, replay after block,
missing CSRF and private text in application logs.
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text

from app.infrastructure.database.models import ConsentEvent, Mood, PrivateItem, User
from app.modules.social.models import Connection, HumanMessage
from tests.conftest import add_actor
from tests.social_helpers import key, open_room

pytestmark = pytest.mark.postgres

ALL_SCOPES = ["account", "private_items", "memories", "moods", "consents", "social"]


async def export(client, scopes=ALL_SCOPES):
    created = await client.post("/api/v1/exports", json={"scopes": scopes}, headers=key())
    assert created.status_code == 201, created.text
    download = await client.get(f"/api/v1/exports/{created.json()['id']}/download")
    assert download.status_code == 200, download.text
    return download.json()


async def say(client, room, words):
    response = await client.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": words, "clientMessageId": str(uuid4())},
        headers=key(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_export_contains_own_social_footprint_but_no_peer_content(clients):
    app, actors, refs, room = await open_room(clients)
    (a, _), (b, _) = actors
    await say(a, room, "Lời của A")
    peer_message = await say(b, room, "Lời riêng của B")
    await b.patch(
        "/api/v1/users/me/identity",
        json={"field": "displayName", "value": "Tên thật của B", "expectedVersion": 0},
        headers=key(),
    )
    report = await a.post(
        "/api/v1/reports",
        json={"peerRef": refs[0], "reason": "Kiểm tra", "selectedMessageIds": [peer_message["id"]]},
        headers=key(),
    )
    assert report.status_code == 201, report.text
    data = await export(a)
    social = data["social"]
    assert [m["text"] for m in social["sentMessages"]] == ["Lời của A"]
    assert social["sentMessages"][0]["connection"] == social["connections"][0]["peer"]
    assert social["publishedProfiles"][0]["current"] is True
    assert social["connectionRequests"][0]["direction"] == "outgoing"
    assert social["reportsFiled"] == [
        {
            "reason": "Kiểm tra",
            "status": "received",
            "evidenceMessages": 1,
            "createdAt": social["reportsFiled"][0]["createdAt"],
        }
    ]
    history = data["consents"]["history"]
    assert [(e["purpose"], e["enabled"]) for e in history] == [("MATCH", True)]
    raw = str(data)
    for leaked in ("Lời riêng của B", "Tên thật của B", str(actors[1][1])):
        assert leaked not in raw
    peer = await export(b, ["social"])
    assert peer["social"]["reportsFiled"] == []
    assert [m["text"] for m in peer["social"]["sentMessages"]] == ["Lời riêng của B"]
    assert peer["social"]["identity"][0]["value"] == "Tên thật của B"
    c, _ = await add_actor(app, 3)
    outsider = await export(c)
    assert outsider["social"]["connections"] == [] and outsider["social"]["sentMessages"] == []
    assert "Lời của A" not in str(outsider)


async def test_export_download_is_bound_to_owner_and_session(clients):
    app, actors = clients
    (a, uid), (b, _) = actors
    created = (
        await a.post("/api/v1/exports", json={"scopes": ["consents"]}, headers=key())
    ).json()
    assert (await b.get(f"/api/v1/exports/{created['id']}/download")).status_code == 404
    assert (await b.get(f"/api/v1/exports/{created['id']}")).status_code == 404
    # A second session of the same account cannot collect the first session's file.
    import hashlib

    from app.infrastructure.database.models import AuthSession

    token, sid = f"second-{uuid4()}", uuid4()
    async with app.state.database.sessions.begin() as db:
        first = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        db.add(
            AuthSession(
                user_id=uid,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                csrf_hash=first.csrf_hash,
                provider_session_id=sid,
                expires_at=first.expires_at,
            )
        )
        await db.execute(
            text("insert into auth.sessions(id,user_id) values (:id,:uid)"), {"id": sid, "uid": uid}
        )
    import httpx

    other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    other.cookies.set("moodprint_session", token)
    try:
        assert (await other.get(f"/api/v1/exports/{created['id']}/download")).status_code == 410
    finally:
        await other.aclose()
    assert (await a.get(f"/api/v1/exports/{created['id']}/download")).status_code == 200


async def test_oversize_export_fails_gracefully(clients):
    app, actors = clients
    a, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            ConsentEvent(user_id=uid, purpose="AI", enabled=True, version=n, policy_version="v1")
            for n in range(1001)
        )
    response = await a.post("/api/v1/exports", json={"scopes": ["consents"]}, headers=key())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EXPORT_TOO_LARGE"
    # No support channel or partial export exists, so the message must not promise one.
    assert "yêu cầu hỗ trợ" not in response.json()["error"]["message"]
    assert (await a.get("/api/v1/session")).status_code == 200


async def test_mood_deletion_scope_removes_only_moods(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    (a, uid), (b, other) = actors
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    body = {"value": 3, "note": "xóa tôi", "timezone": "Asia/Bangkok", "expectedVersion": 0}
    for client in (a, b):
        assert (await client.put(f"/api/v1/moods/{today}", json=body, headers=key())).status_code == 200
    await a.post("/api/v1/profiles/private-items", json={"text": "Giữ lại"}, headers=key())
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    job = await a.post(
        "/api/v1/data-deletions", json={"scope": "moods", "expectedVersion": version}, headers=key()
    )
    assert job.status_code == 202, job.text
    assert (await a.get("/api/v1/moods")).status_code == 409
    await process_deletions(app)
    await process_deletions(app)
    assert (await a.get(f"/api/v1/data-deletions/{job.json()['id']}")).json()["status"] == "completed"
    assert (await a.get("/api/v1/moods")).json() == []
    assert len((await b.get("/api/v1/moods")).json()) == 1
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).where(Mood.user_id == uid)) == 0
        assert await db.scalar(select(func.count()).where(PrivateItem.user_id == uid)) == 1


async def test_account_deletion_closes_rooms_masks_text_and_ends_the_old_session(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors, _, room = await open_room(clients)
    (a, uid), (b, _) = actors
    await say(a, room, "Tin của người sẽ xóa tài khoản")
    await say(b, room, "Tin của người ở lại")
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    deletion = await a.post(
        "/api/v1/data-deletions", json={"scope": "account", "expectedVersion": version}, headers=key()
    )
    assert deletion.status_code == 202, deletion.text
    assert (await a.get("/api/v1/moods")).status_code == 401
    assert (await b.get(f"/api/v1/connections/{room}/messages")).status_code == 403
    await process_deletions(app)
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        assert user.status == "deleted"
        assert (await db.get(Connection, UUID(room))).status != "open"
        texts = (
            await db.scalars(
                select(HumanMessage.text)
                .where(HumanMessage.connection_id == UUID(room))
                .order_by(HumanMessage.seq)
            )
        ).all()
    assert texts == ["[Đã xóa]", "Tin của người ở lại"]
    assert (await a.get("/api/v1/session")).status_code == 401
    again = await a.post(
        "/api/v1/data-deletions", json={"scope": "account", "expectedVersion": version}, headers=key()
    )
    assert again.status_code == 401
    assert (await b.get("/api/v1/matching/candidates")).json()["candidates"] == []


async def test_unrelated_user_cannot_read_write_or_guess_a_pair_room(clients):
    app, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    await say(a, room, "Chỉ A và B")
    c, _ = await add_actor(app, 3)
    for path in (
        f"/api/v1/connections/{room}",
        f"/api/v1/connections/{room}/messages",
        f"/api/v1/connections/{room}/reveal-requests",
        f"/api/v1/connections/{uuid4()}/messages",
    ):
        response = await c.get(path)
        assert response.status_code == 404, path
        assert "Chỉ A và B" not in response.text
    for path, body in (
        (f"/api/v1/connections/{room}/messages", {"text": "chen ngang", "clientMessageId": str(uuid4())}),
        (f"/api/v1/connections/{room}/end", {"expectedVersion": 1}),
        (f"/api/v1/connections/{room}/block", {}),
        (f"/api/v1/connections/{room}/peer-reference", {}),
    ):
        assert (await c.post(path, json=body, headers=key())).status_code == 404, path
    async with app.state.database.sessions() as db:
        assert await db.scalar(
            select(func.count()).where(HumanMessage.connection_id == UUID(room))
        ) == 1


async def test_replayed_send_after_block_is_denied(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    headers = key()
    body = {"text": "trước khi bị chặn", "clientMessageId": str(uuid4())}
    assert (
        await a.post(f"/api/v1/connections/{room}/messages", json=body, headers=headers)
    ).status_code == 201
    assert (await b.post(f"/api/v1/connections/{room}/block", json={}, headers=key())).status_code == 201
    replay = await a.post(f"/api/v1/connections/{room}/messages", json=body, headers=headers)
    assert replay.status_code == 403
    fresh = await a.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "sau khi bị chặn", "clientMessageId": str(uuid4())},
        headers=key(),
    )
    assert fresh.status_code == 403


async def test_writes_without_csrf_or_from_foreign_origin_are_denied(clients):
    _, actors = clients
    a, _ = actors[0]
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    body = {"value": 3, "note": "", "timezone": "Asia/Bangkok", "expectedVersion": 0}
    csrf = a.headers.pop("X-CSRF-Token")
    try:
        denied = await a.put(f"/api/v1/moods/{today}", json=body, headers=key())
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "CSRF_DENIED"
    finally:
        a.headers["X-CSRF-Token"] = csrf
    foreign = await a.put(
        f"/api/v1/moods/{today}", json=body, headers={**key(), "Origin": "https://evil.example"}
    )
    assert foreign.status_code == 403
    assert (await a.get("/api/v1/moods")).json() == []


async def test_private_text_never_reaches_application_logs(clients, caplog):
    caplog.set_level(logging.DEBUG)
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    canaries = ["NOTE_CANARY_7f3", "MESSAGE_CANARY_9a1"]
    await a.put(
        f"/api/v1/moods/{today}",
        json={"value": 2, "note": canaries[0], "timezone": "Asia/Bangkok", "expectedVersion": 0},
        headers=key(),
    )
    await say(b, room, canaries[1])
    await a.get(f"/api/v1/connections/{room}/messages")
    for canary in canaries:
        assert canary not in caplog.text
