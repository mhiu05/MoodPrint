"""T-MOD-02: suspension and social restriction are enforced everywhere."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.core.security import Actor
from app.infrastructure.database.models import AuthSession, User
from app.modules.activities.models import ActivitySession
from tests.activity_helpers import enable, invite, started
from tests.social_helpers import key, publish
from tests.test_moderation_admin import grant, reported

pytestmark = pytest.mark.postgres


async def resolve(staff, report_id, action, days=7):
    response = await staff.post(
        f"/api/v1/admin/reports/{report_id}/resolve",
        json={"expectedVersion": 1, "action": action, "days": days},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_suspension_ends_sessions_streams_and_blocks_login(clients):
    from app.modules.social.notifications import event_stream

    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    rooms = (await a.get("/api/v1/connections")).json()
    async with app.state.database.sessions() as db:
        own = await db.scalar(select(AuthSession).where(AuthSession.user_id == b_id))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": app,
            "query_string": b"",
        }
    )
    events = event_stream(request, Actor(b_id, own.id, 1), UUID(rooms[0]["id"]), after_seq=0)
    assert "messages_available" in await anext(events)
    await resolve(staff, report_id, "suspend")
    assert "access_revoked" in await asyncio.wait_for(anext(events), 6)
    await events.aclose()
    assert (await b.get("/api/v1/session")).status_code in (401, 403)
    async with app.state.database.sessions() as db:
        user = await db.get(User, b_id)
    assert user.suspended_until is not None
    assert (await a.get("/api/v1/connections")).json() == []


async def test_restriction_removes_social_access_and_aborts_activities(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    enable(app)
    room = (await a.get("/api/v1/connections")).json()[0]["id"]
    view = await started(a, b, room)
    await resolve(staff, report_id, "restrict")
    async with app.state.database.sessions() as db:
        session = await db.get(ActivitySession, UUID(view["id"]))
    assert (session.state, session.end_reason) == ("aborted", "account_restricted")
    for path in ("/api/v1/matching/candidates", "/api/v1/connections"):
        denied = await b.get(path)
        assert denied.status_code == 403
    assert (await b.get("/api/v1/session")).json()["notices"][0]["kind"] == "restricted"
    assert (await a.get("/api/v1/connections")).json() == []
    sent = await b.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "vẫn gửi?", "clientMessageId": str(uuid4())},
        headers=key(),
    )
    assert sent.status_code == 403
    assert (await invite(b, room)).status_code == 403


async def test_restricted_user_is_absent_from_discovery_until_lifted(clients):
    from tests.conftest import add_actor

    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id, "admin")
    c, _ = await add_actor(app, 5)
    await publish(c)
    assert len((await c.get("/api/v1/matching/candidates")).json()["candidates"]) == 2
    await resolve(staff, report_id, "restrict")
    assert len((await c.get("/api/v1/matching/candidates")).json()["candidates"]) == 1
    ref = (await staff.get("/api/v1/admin/reports?status=resolved")).json()[0]["subjectRef"]
    lifted = await staff.post(f"/api/v1/admin/users/{ref}/lift", json={"note": ""}, headers=key())
    assert lifted.status_code == 200, lifted.text
    assert len((await c.get("/api/v1/matching/candidates")).json()["candidates"]) == 2
    assert (await b.get("/api/v1/session")).json()["notices"] == []
