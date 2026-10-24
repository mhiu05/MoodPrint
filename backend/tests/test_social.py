"""Real PostgreSQL tests for published matching and two-actor social authorization.

Breaks caught: bypassed preview/version gates, private DTO leakage, wrong hard
filters, duplicate mutual rooms/messages, account quota bypass and stale access.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.social.models import Connection, HumanMessage

pytestmark = pytest.mark.postgres

PROFILE = {
    "interests": ["reading", "music", "walking"],
    "values": ["respect", "sincerity"],
    "style": "balanced",
    "goal": "friendship",
    "languages": ["vi"],
}


def key():
    return {"Idempotency-Key": str(uuid4())}


async def consent(client, enabled=True, expected=1):
    response = await client.put(
        "/api/v1/consents/MATCH",
        json={"enabled": enabled, "expectedVersion": expected, "policyVersion": "v1"},
        headers=key(),
    )
    assert response.status_code == 200, response.text


async def publish(client, profile=None):
    await consent(client)
    response = await client.put(
        "/api/v1/profiles/matching-draft",
        json={**(profile or PROFILE), "expectedVersion": 0},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    response = await client.post("/api/v1/profiles/matching-draft/preview")
    assert response.status_code == 200, response.text
    preview = response.json()
    response = await client.post(
        "/api/v1/profiles/published",
        json={
            "draftVersion": preview["draftVersion"],
            "previewDigest": preview["previewDigest"],
            "expectedPublishedVersion": 0,
        },
        headers=key(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def published_pair(clients):
    app, actors = clients
    for client, _ in actors:
        await publish(client)
    refs = []
    for client, _ in actors:
        response = await client.get("/api/v1/matching/candidates")
        assert response.status_code == 200, response.text
        assert len(response.json()["candidates"]) == 1
        refs.append(response.json()["candidates"][0]["candidateRef"])
    return app, actors, refs


async def open_room(clients):
    app, actors, refs = await published_pair(clients)
    response = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert response.status_code == 201, response.text
    pending = response.json()
    response = await actors[1][0].post(
        f"/api/v1/connection-requests/{pending['id']}/accept",
        json={"expectedVersion": pending["version"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    return app, actors, refs, response.json()["connectionId"]


async def test_publish_requires_current_preview_and_rejects_private_fields(clients):
    _, actors = clients
    client = actors[0][0]
    await consent(client)
    response = await client.put(
        "/api/v1/profiles/matching-draft",
        json={**PROFILE, "expectedVersion": 0, "gender": "private"},
        headers=key(),
    )
    assert response.status_code == 422
    response = await client.put(
        "/api/v1/profiles/matching-draft", json={**PROFILE, "expectedVersion": 0}, headers=key()
    )
    assert response.status_code == 200
    response = await client.post(
        "/api/v1/profiles/published",
        json={"draftVersion": 1, "previewDigest": "forged", "expectedPublishedVersion": 0},
        headers=key(),
    )
    assert response.status_code == 409
    preview = (await client.post("/api/v1/profiles/matching-draft/preview")).json()
    await client.put(
        "/api/v1/profiles/matching-draft",
        json={**PROFILE, "style": "direct", "expectedVersion": 1},
        headers=key(),
    )
    response = await client.post(
        "/api/v1/profiles/published", json={**preview, "expectedPublishedVersion": 0}, headers=key()
    )
    assert response.status_code in (409, 422)


async def test_ai_off_matching_returns_only_public_pair_scoped_cards(clients):
    _, actors, refs = await published_pair(clients)
    first = (await actors[0][0].get("/api/v1/matching/candidates")).json()["candidates"][0]
    assert len(first["reasons"]) <= 3
    assert first["scoringVersion"] == "rules-v1-id"
    assert first["profile"] == PROFILE
    assert not ({"userId", "identity", "privateItems", "sources", "memory", "score"} & first.keys())
    response = await actors[1][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert response.status_code == 404


async def test_goal_and_language_filters_never_create_synthetic_people(clients):
    _, actors = clients
    await publish(actors[0][0])
    await publish(actors[1][0], {**PROFILE, "languages": ["en"]})
    response = await actors[0][0].get("/api/v1/matching/candidates")
    assert response.status_code == 200
    assert response.json()["candidates"] == []


async def test_teen_and_revoked_match_cannot_publish_or_reuse_candidates(clients):
    app, actors, refs = await published_pair(clients)
    await consent(actors[1][0], False, 2)
    response = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert response.status_code == 403
    await consent(actors[1][0], True, 3)
    assert (await actors[0][0].get("/api/v1/matching/candidates")).json()["candidates"] == []
    from app.infrastructure.database.models import User

    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, actors[0][1])
        user.age_band = "teen"
    response = await actors[0][0].get("/api/v1/matching/candidates")
    assert response.status_code == 403


async def test_cross_invites_concurrently_open_exactly_one_room(clients):
    app, actors, refs = await published_pair(clients)
    responses = await asyncio.gather(
        *[
            actor[0].post("/api/v1/connection-requests", json={"candidateRef": ref}, headers=key())
            for actor, ref in zip(actors, refs, strict=True)
        ]
    )
    assert [response.status_code for response in responses] == [201, 201]
    rooms = [(await actor[0].get("/api/v1/connections")).json() for actor in actors]
    assert len(rooms[0]) == len(rooms[1]) == 1
    assert rooms[0][0]["id"] == rooms[1][0]["id"]

    async with app.state.database.sessions() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Connection).where(Connection.status == "open")
            )
            == 1
        )


async def test_sender_cannot_accept_and_duplicate_accept_returns_same_room(clients):
    _, actors, refs = await published_pair(clients)
    pending = (
        await actors[0][0].post(
            "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
        )
    ).json()
    path = f"/api/v1/connection-requests/{pending['id']}/accept"
    response = await actors[0][0].post(path, json={"expectedVersion": 1}, headers=key())
    assert response.status_code == 403
    headers = key()
    first = await actors[1][0].post(path, json={"expectedVersion": 1}, headers=headers)
    second = await actors[1][0].post(path, json={"expectedVersion": 1}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["connectionId"] == second.json()["connectionId"]


async def test_message_commit_retry_payload_conflict_and_block_live_deny(clients):
    app, actors, refs, room = await open_room(clients)
    headers = key()
    message_id = str(uuid4())
    body = {"clientMessageId": message_id, "text": "Xin chào"}
    path = f"/api/v1/connections/{room}/messages"
    first = await actors[0][0].post(path, json=body, headers=headers)
    second = await actors[0][0].post(path, json=body, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["seq"] == "1"
    reused_key = await actors[0][0].post(
        path, json={"clientMessageId": str(uuid4()), "text": "Một ý định khác"}, headers=headers
    )
    assert reused_key.status_code == 409
    conflict = await actors[0][0].post(path, json={**body, "text": "Khác"}, headers=key())
    assert conflict.status_code == 409
    history = await actors[1][0].get(path)
    assert [m["text"] for m in history.json()["messages"]] == ["Xin chào"]
    response = await actors[0][0].post("/api/v1/blocks", json={"peerRef": refs[0]}, headers=key())
    assert response.status_code == 201
    assert (await actors[1][0].get(path)).status_code == 403
    assert (
        await actors[1][0].post(
            path, json={"clientMessageId": str(uuid4()), "text": "blocked"}, headers=key()
        )
    ).status_code == 403

    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(HumanMessage)) == 1


async def test_message_quota_is_not_consumed_twice_by_retry(clients):
    _, actors, _, room = await open_room(clients)
    path = f"/api/v1/connections/{room}/messages"
    body = {"clientMessageId": str(uuid4()), "text": "A"}
    for _ in range(2):
        assert (await actors[0][0].post(path, json=body, headers=key())).status_code == 201
    for _ in range(19):
        response = await actors[0][0].post(
            path, json={"clientMessageId": str(uuid4()), "text": "A"}, headers=key()
        )
        assert response.status_code == 201
    assert (
        await actors[0][0].post(
            path, json={"clientMessageId": str(uuid4()), "text": "A"}, headers=key()
        )
    ).status_code == 429


async def test_republish_and_match_reenable_never_resurrect_room(clients):
    _, actors, _, room = await open_room(clients)
    path = f"/api/v1/connections/{room}/messages"
    await consent(actors[0][0], False, 2)
    assert (await actors[1][0].get(path)).status_code == 403
    await consent(actors[0][0], True, 3)
    assert (await actors[1][0].get(path)).status_code == 403
