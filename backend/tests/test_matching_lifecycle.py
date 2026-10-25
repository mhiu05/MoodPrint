"""Real PostgreSQL tests for the matching/connection lifecycle edges.

Breaks caught: private edits silently unpublishing profiles, a stale "shared"
view that can never be withdrawn, implicit republish after consent restore,
quota blocking a mutual match, missing cooldowns, unbounded message pages,
deleted accounts in discovery and evidence-free reporting after a block.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.infrastructure.database.models import User, now
from app.modules.social.models import (
    CandidateReference,
    Connection,
    ConnectionRequest,
    HumanMessage,
    Pair,
)
from tests.conftest import add_actor
from tests.social_helpers import consent, key, open_room, publish, published_pair

pytestmark = pytest.mark.postgres


async def republish(client):
    draft = (await client.get("/api/v1/profiles/matching-draft")).json()
    preview = (await client.post("/api/v1/profiles/matching-draft/preview")).json()
    response = await client.post(
        "/api/v1/profiles/published",
        json={
            "draftVersion": preview["draftVersion"],
            "previewDigest": preview["previewDigest"],
            "expectedPublishedVersion": draft["publishedVersion"],
        },
        headers=key(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_private_item_edits_keep_the_profile_live_and_rooms_open(clients):
    _, actors, _, room = await open_room(clients)
    a = actors[0][0]
    item = (
        await a.post("/api/v1/profiles/private-items", json={"text": "Riêng tư"}, headers=key())
    ).json()
    edited = await a.patch(
        f"/api/v1/profiles/private-items/{item['id']}",
        json={"text": "Đã sửa", "expectedVersion": 1},
        headers=key(),
    )
    assert edited.status_code == 200, edited.text
    deleted = await a.request(
        "DELETE",
        f"/api/v1/profiles/private-items/{item['id']}",
        json={"expectedVersion": 2},
        headers=key(),
    )
    assert deleted.status_code == 200, deleted.text
    assert (await a.get(f"/api/v1/connections/{room}")).status_code == 200
    assert (await actors[1][0].get(f"/api/v1/connections/{room}/messages")).status_code == 200
    assert (await a.get("/api/v1/profiles/published/current")).json()["state"] == "live"


async def test_consent_restore_requires_explicit_republish_and_stale_profile_can_be_withdrawn(
    clients,
):
    _, actors = clients
    a = actors[0][0]
    published = await publish(a)
    assert published["state"] == "live"
    current = (await a.get("/api/v1/profiles/published/current")).json()
    assert (current["state"], current["profileVersion"]) == ("live", published["profileVersion"])
    await consent(a, False, 2)
    await consent(a, True, 3)
    stale = (await a.get("/api/v1/profiles/published/current")).json()
    assert stale["state"] == "needs_republish"
    denied = await a.get("/api/v1/matching/candidates")
    assert denied.json()["error"]["code"] == "PROFILE_REQUIRED"
    fresh = await republish(a)
    assert fresh["state"] == "live" and fresh["profileVersion"] == stale["profileVersion"] + 1
    await consent(a, False, 4)
    withdrawn = await a.request(
        "DELETE",
        "/api/v1/profiles/published/current",
        json={"expectedVersion": fresh["profileVersion"]},
        headers=key(),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert (await a.get("/api/v1/profiles/published/current")).json() is None


async def test_sending_back_completes_a_match_even_at_invitation_quota(clients):
    app, actors, refs = await published_pair(clients)
    (a, a_id), (b, _) = actors
    sent = await a.post("/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key())
    assert sent.status_code == 201
    async with app.state.database.sessions.begin() as db:
        # Ten other invitations from B in the last day exhaust B's daily quota.
        for _ in range(10):
            peer = uuid4()
            db.add(User(id=peer, auth_subject=peer, age_band="adult"))
            await db.flush()
            low, high = sorted((actors[1][1], peer))
            pair = Pair(low_user_id=low, high_user_id=high)
            db.add(pair)
            await db.flush()
            db.add(
                ConnectionRequest(
                    pair_id=pair.id,
                    sender_id=actors[1][1],
                    recipient_id=peer,
                    snapshots={},
                    status="declined",
                    expires_at=now() + timedelta(days=7),
                )
            )
    back = await b.post("/api/v1/connection-requests", json={"candidateRef": refs[1]}, headers=key())
    assert back.status_code == 201, back.text
    assert back.json()["status"] == "accepted" and back.json()["connectionId"]
    async with app.state.database.sessions() as db:
        rooms = (
            await db.scalars(
                select(Connection).where(
                    (Connection.low_user_id == a_id) | (Connection.high_user_id == a_id)
                )
            )
        ).all()
        assert len(rooms) == 1


@pytest.mark.parametrize("action", ["skip", "decline", "cancel"])
async def test_skip_decline_and_cancel_apply_a_pair_cooldown(clients, action):
    app, actors, refs = await published_pair(clients)
    (a, _), (b, _) = actors
    if action == "skip":
        response = await a.post("/api/v1/matching/skips", json={"candidateRef": refs[0]}, headers=key())
        assert response.status_code == 200, response.text
    else:
        sent = (
            await a.post("/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key())
        ).json()
        actor = b if action == "decline" else a
        wrong = a if action == "decline" else b
        body = {"expectedVersion": sent["version"]}
        assert (
            await wrong.post(f"/api/v1/connection-requests/{sent['id']}/{action}", json=body, headers=key())
        ).status_code == 403
        response = await actor.post(
            f"/api/v1/connection-requests/{sent['id']}/{action}", json=body, headers=key()
        )
        assert response.status_code == 200, response.text
    for client in (a, b):
        assert (await client.get("/api/v1/matching/candidates")).json()["candidates"] == []
    async with app.state.database.sessions() as db:
        pair = await db.scalar(select(Pair))
        assert pair.cooldown_until > now() + timedelta(days=29)


async def test_ended_connection_denies_reads_and_sends_for_both_sides(clients):
    _, actors, _, room = await open_room(clients)
    (a, _), (b, _) = actors
    view = (await a.get(f"/api/v1/connections/{room}")).json()
    ended = await a.post(
        f"/api/v1/connections/{room}/end", json={"expectedVersion": view["version"]}, headers=key()
    )
    assert ended.status_code == 200, ended.text
    for client in (a, b):
        assert (await client.get(f"/api/v1/connections/{room}/messages")).status_code == 403
        sent = await client.post(
            f"/api/v1/connections/{room}/messages",
            json={"text": "còn đó không?", "clientMessageId": str(uuid4())},
            headers=key(),
        )
        assert sent.status_code == 403
        assert (await client.get("/api/v1/connections")).json() == []


async def test_message_history_pages_in_order_beyond_one_hundred(clients):
    app, actors, _, room = await open_room(clients)
    (a, a_id), (b, b_id) = actors
    async with app.state.database.sessions.begin() as db:
        connection = await db.get(Connection, UUID(room))
        for seq in range(1, 131):
            db.add(
                HumanMessage(
                    connection_id=connection.id,
                    sender_id=a_id if seq % 2 else b_id,
                    client_message_id=uuid4(),
                    text=f"tin {seq}",
                    seq=seq,
                )
            )
        connection.next_seq = 130
    first = (await b.get(f"/api/v1/connections/{room}/messages")).json()
    assert [m["seq"] for m in first["messages"]] == [str(n) for n in range(1, 101)]
    assert first["highWaterSeq"] == "130"
    rest = (
        await b.get(f"/api/v1/connections/{room}/messages", params={"afterSeq": "100"})
    ).json()
    assert [m["text"] for m in rest["messages"]] == [f"tin {n}" for n in range(101, 131)]
    assert {m["sender"] for m in rest["messages"]} == {"self", "peer"}


@pytest.mark.parametrize("state", [{"deletion_pending": True}, {"status": "deleted"}])
async def test_deleting_or_deleted_accounts_leave_discovery(clients, state):
    app, actors, _ = await published_pair(clients)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == actors[1][1]).values(**state))
    assert (await actors[0][0].get("/api/v1/matching/candidates")).json()["candidates"] == []


async def test_discovery_backfills_peers_that_fail_the_locked_recheck(clients, monkeypatch):
    app, actors = clients
    await publish(actors[0][0])
    peers = [await add_actor(app, 10 + i) for i in range(7)]
    for client, _ in peers:
        await publish(client)
    gone = [uid for _, uid in peers[:2]]
    from app.modules.social import retrieval

    ranked = retrieval.ranked_candidates

    async def racing(db, user, own, consent):
        # Simulates two shortlisted peers deleting their accounts between ranking
        # and the locked recheck: they must be skipped and replaced.
        result = await ranked(db, user, own, consent)
        await db.execute(update(User).where(User.id.in_(gone)).values(status="deleted"))
        return gone + [peer for peer in result if peer not in gone]

    monkeypatch.setattr(retrieval, "ranked_candidates", racing)
    cards = (await actors[0][0].get("/api/v1/matching/candidates")).json()["candidates"]
    assert len(cards) == 5
    assert retrieval.SHORTLIST >= 7
    async with app.state.database.sessions() as db:
        shown = (await db.scalars(select(CandidateReference.peer_id))).all()
    assert not set(shown) & set(gone)


async def test_report_after_block_keeps_pair_evidence_and_is_rate_limited(clients):
    app, actors, refs, room = await open_room(clients)
    (a, _), (b, _) = actors
    message = (
        await b.post(
            f"/api/v1/connections/{room}/messages",
            json={"text": "Tin nhắn quấy rối", "clientMessageId": str(uuid4())},
            headers=key(),
        )
    ).json()
    assert (await a.post(f"/api/v1/connections/{room}/block", json={}, headers=key())).status_code == 201
    ref = (
        await a.post(f"/api/v1/connections/{room}/peer-reference", json={}, headers=key())
    ).json()["peerRef"]
    body = {"peerRef": ref, "reason": "Quấy rối", "selectedMessageIds": [message["id"]]}
    report = await a.post("/api/v1/reports", json=body, headers=key())
    assert report.status_code == 201, report.text
    # A third, unrelated account cannot attach this pair's messages as evidence.
    c, _ = await add_actor(app, 3)
    foreign_room = await c.post(f"/api/v1/connections/{room}/peer-reference", json={}, headers=key())
    assert foreign_room.status_code == 404
    for _ in range(4):
        assert (
            await a.post("/api/v1/reports", json={**body, "selectedMessageIds": []}, headers=key())
        ).status_code == 201
    limited = await a.post("/api/v1/reports", json={**body, "selectedMessageIds": []}, headers=key())
    assert limited.status_code == 429
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(CandidateReference)
            .where(CandidateReference.id == UUID(ref))
            .values(expires_at=now() - timedelta(minutes=1))
        )
    expired = await b.post(
        "/api/v1/reports", json={**body, "selectedMessageIds": []}, headers=key()
    )
    assert expired.status_code == 404  # B cannot use A's reference at all


async def test_expired_reference_cannot_open_a_report(clients):
    app, actors, refs, room = await open_room(clients)
    a = actors[0][0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(CandidateReference)
            .where(CandidateReference.id == UUID(refs[0]))
            .values(expires_at=now() - timedelta(minutes=1))
        )
    response = await a.post(
        "/api/v1/reports", json={"peerRef": refs[0], "reason": "Spam"}, headers=key()
    )
    assert response.status_code == 410


async def test_expired_references_are_purged(clients):
    app, actors, refs = await published_pair(clients)
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(CandidateReference)
            .where(CandidateReference.id == UUID(refs[0]))
            .values(expires_at=now() - timedelta(days=2))
        )
    from app.jobs.retention import purge_expired

    await purge_expired(app)
    async with app.state.database.sessions() as db:
        remaining = (await db.scalars(select(CandidateReference.id))).all()
    assert UUID(refs[0]) not in remaining and UUID(refs[1]) in remaining
