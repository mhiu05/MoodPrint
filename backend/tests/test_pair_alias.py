"""DR-06: one pseudonymous alias per pair across candidates, connections and export."""

import pytest

from tests.social_helpers import key, published_pair

pytestmark = pytest.mark.postgres


async def test_candidate_connection_and_export_share_one_pair_alias(clients):
    app, actors, refs = await published_pair(clients)
    aliases = [
        (await client.get("/api/v1/matching/candidates")).json()["candidates"][0]["alias"]
        for client, _ in actors
    ]
    assert aliases[0] == aliases[1]
    response = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    pending = response.json()
    response = await actors[1][0].post(
        f"/api/v1/connection-requests/{pending['id']}/accept",
        json={"expectedVersion": pending["version"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    for client, _ in actors:
        rooms = (await client.get("/api/v1/connections")).json()
        assert [room["alias"] for room in rooms] == [aliases[0]]
        job = (
            await client.post("/api/v1/exports", json={"scopes": ["social"]}, headers=key())
        ).json()
        exported = (await client.get(f"/api/v1/exports/{job['id']}/download")).json()
        assert [row["peer"] for row in exported["social"]["connections"]] == [aliases[0]]
