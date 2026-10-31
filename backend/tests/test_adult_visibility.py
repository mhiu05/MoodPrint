"""Real PostgreSQL regressions for peer privacy and background adult eligibility.

An adult age-band cache alone must never expose a peer or authorize paid memory
processing when the authoritative declaration is missing, invalid or underage.
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.infrastructure.database.models import AgeDeclaration, now
from tests.social_helpers import key, open_room, published_pair
from tests.test_embeddings import (
    SyntheticProvider,
    add_memory,
    embedding_env,  # noqa: F401 -- reuse the real embedding integration environment
    queue_memory,
)

pytestmark = pytest.mark.postgres


async def invalidate_declaration(db, uid, condition):
    declaration = await db.get(AgeDeclaration, uid)
    if declaration is None:
        declaration = AgeDeclaration(
            user_id=uid,
            birth_year=1990,
            policy_version="self-declared-age-v1",
        )
        db.add(declaration)
        await db.flush()
    if condition == "missing":
        await db.delete(declaration)
    elif condition == "minor":
        declaration.birth_year = now().year - 17
    elif condition == "unconfirmed-boundary":
        declaration.birth_year = now().year - 18
        declaration.adult_confirmed_at = None
    elif condition == "future-confirmation":
        declaration.birth_year = now().year - 18
        declaration.adult_confirmed_at = now() + timedelta(days=1)
    elif condition == "unsupported-policy":
        declaration.policy_version = "unknown-age-policy"
    else:
        raise AssertionError(condition)


@pytest.mark.parametrize(
    "condition",
    ["missing", "minor", "unconfirmed-boundary", "future-confirmation", "unsupported-policy"],
)
async def test_invalid_peer_declaration_hides_published_profile_and_rejects_old_reference(
    clients, condition
):
    app, actors, refs = await published_pair(clients)
    async with app.state.database.sessions.begin() as db:
        await invalidate_declaration(db, actors[1][1], condition)
    response = await actors[0][0].get("/api/v1/matching/candidates")
    assert response.status_code == 200
    assert response.json()["candidates"] == []
    response = await actors[0][0].post(
        "/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key()
    )
    assert response.status_code == 403


async def test_invalid_peer_declaration_hides_room_and_message_preview(clients):
    app, actors, _, room = await open_room(clients)
    response = await actors[1][0].post(
        f"/api/v1/connections/{room}/messages",
        json={"clientMessageId": str(uuid4()), "text": "PRIVATE_PREVIEW_SENTINEL"},
        headers=key(),
    )
    assert response.status_code == 201
    async with app.state.database.sessions.begin() as db:
        await invalidate_declaration(db, actors[1][1], "missing")
    response = await actors[0][0].get("/api/v1/connections")
    assert response.status_code == 200
    assert response.json() == []
    response = await actors[0][0].get(f"/api/v1/connections/{room}")
    assert response.status_code == 403


async def test_revoked_declaration_prevents_queued_memory_provider_dispatch(embedding_env):  # noqa: F811
    from app.ai.embeddings import process_embedding_jobs

    database, settings, actor, _ = embedding_env
    memory_id = await add_memory(database, actor.user_id)
    await queue_memory(database, settings, memory_id)
    async with database.sessions.begin() as db:
        await invalidate_declaration(db, actor.user_id, "missing")
    provider = SyntheticProvider()
    await process_embedding_jobs(database, settings, provider=provider)
    assert provider.calls == []
