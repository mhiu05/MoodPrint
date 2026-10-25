"""The outbox had no consumer (DR-10): nothing writes it and retention drains it."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.infrastructure.database.models import Outbox
from tests.social_helpers import consent, key, open_room

pytestmark = pytest.mark.postgres


async def outbox_rows(app):
    async with app.state.database.sessions() as db:
        return await db.scalar(select(func.count()).select_from(Outbox))


async def test_social_and_consent_writes_never_append_outbox_rows(clients):
    app, actors, _, room = await open_room(clients)
    response = await actors[0][0].post(
        f"/api/v1/connections/{room}/messages",
        json={"clientMessageId": str(uuid4()), "text": "xin chào"},
        headers=key(),
    )
    assert response.status_code == 201, response.text
    response = await actors[0][0].post(
        f"/api/v1/connections/{room}/block", json={}, headers=key()
    )
    assert response.status_code == 201, response.text
    await consent(actors[1][0], enabled=False, expected=2)
    assert await outbox_rows(app) == 0


async def test_retention_purges_existing_outbox_rows(clients):
    from app.jobs.retention import purge_expired

    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            Outbox(user_id=actors[0][1], kind="profile_changed", resource_id=str(i), version=1)
            for i in range(3)
        )
    await purge_expired(app)
    assert await outbox_rows(app) == 0
