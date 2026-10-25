from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import now
from app.modules.social.models import Connection, ConnectionRequest, Pair
from tests.social_helpers import consent, key, open_room, published_pair

pytestmark = pytest.mark.postgres


async def test_expired_invitation_cooldown_uses_expiry_instead_of_last_attempt(clients):
    app, actors, refs = await published_pair(clients)
    first = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert first.status_code == 201
    old_id = UUID(first.json()["id"])
    async with app.state.database.sessions.begin() as db:
        pending = await db.get(ConnectionRequest, old_id)
        pending.expires_at = now() - timedelta(days=31)
    candidates = (await actors[0][0].get("/api/v1/matching/candidates")).json()["candidates"]
    assert len(candidates) == 1
    response = await actors[0][0].post(
        "/api/v1/connection-requests",
        json={"candidateRef": candidates[0]["candidateRef"]},
        headers=key(),
    )
    assert response.status_code == 201, response.text
    assert response.json()["id"] != str(old_id)
    async with app.state.database.sessions() as db:
        assert (await db.get(ConnectionRequest, old_id)).status == "expired"
        pair = await db.scalar(select(Pair))
        assert pair.cooldown_until < now()


async def test_match_revocation_materializes_closed_room_and_stable_cooldown(clients):
    app, actors, _, room_id = await open_room(clients)
    await consent(actors[0][0], False, 2)
    async with app.state.database.sessions() as db:
        assert (await db.get(Connection, UUID(room_id))).status == "closed"
        pair = await db.scalar(select(Pair))
        deadline = pair.cooldown_until
        assert now() + timedelta(days=29) < deadline <= now() + timedelta(days=30)
    await consent(actors[0][0], True, 3)
    assert (await actors[1][0].get(f"/api/v1/connections/{room_id}/messages")).status_code == 403
    async with app.state.database.sessions() as db:
        assert (await db.scalar(select(Pair))).cooldown_until == deadline
