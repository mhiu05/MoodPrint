import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.postgres


async def test_consent_cas_ledger_and_independent_effective_permissions(clients):
    app, actors = clients
    a, uid = actors[0]
    initial = (await a.get("/api/v1/session")).json()
    assert all(initial["consents"][purpose]["enabled"] for purpose in ("AI", "MEM", "VOICE"))
    assert initial["consents"]["MATCH"]["enabled"] is False
    ignored = await a.put(
        "/api/v1/consents/MEM",
        json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert ignored.status_code == 200, ignored.text
    assert ignored.json()["consents"]["MEM"]["enabled"] is True
    assert ignored.json()["consents"]["MEM"]["version"] == 1
    response = await a.put(
        "/api/v1/consents/MATCH",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    assert response.json()["consents"]["MATCH"]["version"] == 2
    assert response.json()["consents"]["AI"]["enabled"] is True
    stale = await a.put(
        "/api/v1/consents/MATCH",
        json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert stale.status_code == 409
    from app.infrastructure.database.models import ConsentEvent

    async with app.state.database.sessions() as db:
        events = (await db.scalars(select(ConsentEvent).where(ConsentEvent.user_id == uid))).all()
        assert len(events) == 1


async def test_concurrent_consent_updates_only_one_commits(clients):
    _, actors = clients
    a, _ = actors[0]
    responses = await asyncio.gather(
        *[
            a.put(
                "/api/v1/consents/MATCH",
                json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]


async def test_mood_validation_reload_and_stale_write(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    _, actors = clients
    a, _ = actors[0]
    mood_path = f"/api/v1/moods/{datetime.now(ZoneInfo('Asia/Bangkok')).date()}"
    payload = {
        "value": 4,
        "note": "Một ngày yên bình",
        "timezone": "Asia/Bangkok",
        "expectedVersion": 0,
    }
    r = await a.put(mood_path, json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    assert (await a.get("/api/v1/moods")).json()[0]["note"] == "Một ngày yên bình"
    assert (await actors[1][0].get("/api/v1/moods")).json() == []
    stale = await a.put(mood_path, json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert stale.status_code == 409
    for invalid in ({**payload, "value": 6}, {**payload, "timezone": "no-such-zone"}):
        assert (
            await a.put(mood_path, json=invalid, headers={"Idempotency-Key": str(uuid4())})
        ).status_code == 422


async def test_revoked_provider_session_and_logout_immediately_deny(clients):
    app, actors = clients
    a, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("delete from auth.sessions where user_id=:id"), {"id": uid})
    assert (await a.get("/api/v1/memories")).status_code == 401
    b, _ = actors[1]
    assert (await b.post("/api/v1/auth/logout")).status_code == 204
    assert (await b.get("/api/v1/session")).status_code == 401
