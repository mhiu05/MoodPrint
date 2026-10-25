"""Shared two-actor social helpers for real PostgreSQL tests (no fake people)."""

from uuid import uuid4

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


async def republish(client, profile):
    """Edit the draft and publish it again through the reviewed preview flow."""
    draft = (await client.get("/api/v1/profiles/matching-draft")).json()
    response = await client.put(
        "/api/v1/profiles/matching-draft",
        json={**profile, "expectedVersion": draft["version"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
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


async def withdraw(client):
    current = (await client.get("/api/v1/profiles/published/current")).json()
    response = await client.request(
        "DELETE",
        "/api/v1/profiles/published/current",
        json={"expectedVersion": current["profileVersion"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
