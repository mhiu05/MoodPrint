"""Default-deny guest permissions: exact operation map, requester and peer gates, isolation."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from tests.guest_helpers import add_guest
from tests.social_helpers import key, publish

pytestmark = pytest.mark.postgres

PUBLIC = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/bots"),
    ("GET", "/taxonomy"),
    ("GET", "/public/experience"),
    ("POST", "/auth/login"),
    ("POST", "/auth/signup"),
    ("POST", "/auth/confirmation"),
    ("POST", "/auth/password-recovery"),
    ("POST", "/auth/password-reset"),
}
# Own data, owner-scoped, available to a live guest (and registered users) within their policy.
PERSONAL = {
    ("POST", "/feedback"),
    ("GET", "/feedback/submission-state"),
    ("GET", "/session"),
    ("PUT", "/users/me/eligibility"),
    ("POST", "/auth/logout"),
    ("PUT", "/consents/{purpose}"),
    ("GET", "/ai/preferences"),
    ("PUT", "/ai/preferences"),
    ("GET", "/ai/conversations"),
    ("POST", "/ai/conversations"),
    ("GET", "/ai/conversations/{conversation_id}"),
    ("PATCH", "/ai/conversations/{conversation_id}"),
    ("DELETE", "/ai/conversations/{conversation_id}"),
    ("GET", "/ai/conversations/{conversation_id}/export"),
    ("POST", "/ai/conversations/{conversation_id}/end"),
    ("POST", "/ai/conversations/{conversation_id}/messages"),
    ("GET", "/ai/runs/{run_id}/events"),
    ("POST", "/ai/runs/{run_id}/cancel"),
    ("GET", "/memories"),
    ("PATCH", "/memories/{memory_id}"),
    ("DELETE", "/memories/{memory_id}"),
    ("GET", "/proposals"),
    ("POST", "/proposals/{proposal_id}/confirm"),
    ("POST", "/proposals/{proposal_id}/reject"),
    ("GET", "/moods"),
    ("GET", "/moods/summary"),
    ("PUT", "/moods/{local_date}"),
    ("DELETE", "/moods/{local_date}"),
    ("GET", "/journal/entries"),
    ("POST", "/journal/entries"),
    ("GET", "/journal/entries/{entry_id}"),
    ("PUT", "/journal/entries/{entry_id}"),
    ("DELETE", "/journal/entries/{entry_id}"),
    ("POST", "/journal/entries/{entry_id}/media"),
    ("POST", "/journal/entries/{entry_id}/media/{media_id}/complete"),
    ("GET", "/journal/entries/{entry_id}/media/{media_id}/access"),
    ("DELETE", "/journal/entries/{entry_id}/media/{media_id}"),
    ("GET", "/profiles/private-items"),
    ("POST", "/profiles/private-items"),
    ("PATCH", "/profiles/private-items/{item_id}"),
    ("DELETE", "/profiles/private-items/{item_id}"),
    ("GET", "/users/me/identity"),
    ("PATCH", "/users/me/identity"),
    ("POST", "/voice/transcriptions"),
    ("POST", "/exports"),
    ("GET", "/exports/{job_id}"),
    ("GET", "/exports/{job_id}/download"),
    ("POST", "/data-deletions"),
    ("GET", "/data-deletions/{job_id}"),
}
REGISTERED_ONLY = {
    ("GET", "/admin/feedback"),
    ("GET", "/admin/feedback/summary"),
    ("PATCH", "/admin/feedback/{id}"),
    ("GET", "/profiles/matching-draft"),
    ("PUT", "/profiles/matching-draft"),
    ("POST", "/profiles/matching-draft/preview"),
    ("POST", "/profiles/published"),
    ("GET", "/profiles/published/current"),
    ("DELETE", "/profiles/published/current"),
    ("GET", "/matching/candidates"),
    ("POST", "/matching/skips"),
    ("GET", "/connection-requests"),
    ("POST", "/connection-requests"),
    ("POST", "/connection-requests/{request_id}/accept"),
    ("POST", "/connection-requests/{request_id}/decline"),
    ("POST", "/connection-requests/{request_id}/cancel"),
    ("GET", "/connections"),
    ("GET", "/connections/{connection_id}"),
    ("POST", "/connections/{connection_id}/read"),
    ("GET", "/connections/{connection_id}/messages"),
    ("POST", "/connections/{connection_id}/messages"),
    ("POST", "/connections/{connection_id}/end"),
    ("POST", "/connections/{connection_id}/block"),
    ("GET", "/connections/{connection_id}/events"),
    ("POST", "/blocks"),
    ("GET", "/activities/catalog"),
    ("POST", "/connections/{connection_id}/activities"),
    ("GET", "/connections/{connection_id}/activities"),
    ("GET", "/connections/{connection_id}/activities/current"),
    ("GET", "/activities/{session_id}"),
    ("POST", "/activities/{session_id}/accept"),
    ("POST", "/activities/{session_id}/decline"),
    ("POST", "/activities/{session_id}/cancel"),
    ("POST", "/activities/{session_id}/end"),
    ("POST", "/activities/{session_id}/focus/join"),
    ("POST", "/activities/{session_id}/focus/leave"),
    ("POST", "/activities/{session_id}/focus/pause"),
    ("POST", "/activities/{session_id}/focus/resume"),
    ("POST", "/activities/{session_id}/ready"),
    ("POST", "/activities/{session_id}/responses"),
    ("POST", "/activities/{session_id}/feedback"),
    ("POST", "/connections/{connection_id}/peer-reference"),
    ("POST", "/connections/{connection_id}/reveal-requests"),
    ("GET", "/connections/{connection_id}/reveal-requests"),
    ("POST", "/reveal-requests/{reveal_id}/grant"),
    ("POST", "/reveal-requests/{reveal_id}/decline"),
    ("GET", "/reveal-grants/{reveal_id}/value"),
    ("DELETE", "/reveal-grants/{reveal_id}"),
    ("POST", "/reports"),
    ("GET", "/reports/{report_id}"),
    ("POST", "/auth/reauthenticate"),
    ("GET", "/admin/reports"),
    ("POST", "/admin/reports/{report_id}/claim"),
    ("POST", "/admin/reports/{report_id}/resolve"),
    ("POST", "/admin/users/{ref}/lift"),
}
# Deliberate zero projection: no social SQL for a guest, no 403 for the badge poll.
SUMMARY_ZERO = {("GET", "/social/summary")}
# Guest lifecycle entry points added by this feature; each has its own guards (plan 01).
GUEST_ENTRY = {
    ("POST", "/auth/guest-intents"),
    ("POST", "/auth/guest"),
    ("POST", "/auth/guest/end"),
}
CLASSIFIED = {
    "public": PUBLIC,
    "personal": PERSONAL,
    "registered_only": REGISTERED_ONLY,
    "summary_zero": SUMMARY_ZERO,
    "guest_entry": GUEST_ENTRY,
}
SOCIAL_TABLES = (
    "connection_requests",
    "connections",
    "human_messages",
    "published_profiles",
    "matching_drafts",
    "candidate_references",
    "pairs",
    "blocks",
    "connection_reads",
    "reveal_access",
    "activity_sessions",
    "reports",
    "staff_roles",
)


def concrete(path: str) -> str:
    parts = {
        "{purpose}": "MATCH",
        "{local_date}": "2026-01-01",
        "{ref}": "0" * 32,
    }
    for token, value in parts.items():
        path = path.replace(token, value)
    while "{" in path:
        start = path.index("{")
        path = path[:start] + str(uuid4()) + path[path.index("}") + 1 :]
    return path


def actual_operations(app):
    paths = app.openapi()["paths"]
    return {
        (method.upper(), path.removeprefix("/api/v1"))
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }


def test_every_operation_has_guest_policy():
    from app.main import create_app

    classified = [tuple_ for group in CLASSIFIED.values() for tuple_ in group]
    assert len(classified) == len(set(classified)), "an operation is classified twice"
    app = create_app()
    assert actual_operations(app) == set(classified), (
        "every OpenAPI operation needs exactly one guest policy: "
        f"unclassified={sorted(actual_operations(app) - set(classified))} "
        f"obsolete={sorted(set(classified) - actual_operations(app))}"
    )


@pytest.mark.parametrize("method_path", sorted(REGISTERED_ONLY))
async def test_guest_direct_social_routes_denied(clients, method_path):
    app, _ = clients
    method, path = method_path
    # Forged consent: a live adult guest with every purpose (including MATCH) switched on.
    guest = await add_guest(app, consents=True)
    app.state.settings.moderation_admin_enabled = True
    body = {} if method in ("POST", "PUT", "PATCH") else None
    response = await guest.client.request(
        method, "/api/v1" + concrete(path), json=body, headers=key()
    )
    assert response.status_code == 403, (method, path, response.text)
    assert response.json()["error"]["code"] == "REGISTERED_REQUIRED"

    expired = await add_guest(app, started_ago=timedelta(seconds=7200 + 30), consents=True)
    late = await expired.client.request(
        method, "/api/v1" + concrete(path), json=body, headers=key()
    )
    assert late.status_code == 401 and late.json()["error"]["code"] == "GUEST_EXPIRED"


async def test_registered_users_still_reach_social_routes(clients):
    _, actors = clients
    client, _uid = actors[0]
    await publish(client)
    assert (await client.get("/api/v1/connections")).status_code == 200
    assert (await client.get("/api/v1/social/summary")).status_code == 200
    assert (await client.get("/api/v1/matching/candidates")).status_code == 200


async def test_guest_cannot_enable_match_but_may_withdraw_it(clients):
    app, _ = clients
    guest = await add_guest(app, consents=True)
    enable = await guest.client.put(
        "/api/v1/consents/MATCH",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert enable.status_code == 403 and enable.json()["error"]["code"] == "REGISTERED_REQUIRED"
    withdraw = await guest.client.put(
        "/api/v1/consents/MATCH",
        json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["consents"]["MATCH"]["enabled"] is False


async def test_guest_summary_does_not_query_social_tables(clients):
    app, _ = clients
    guest = await add_guest(app, consents=True)
    statements: list[str] = []
    engine = app.state.database.engine.sync_engine

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = await guest.client.get("/api/v1/social/summary")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert response.status_code == 200
    assert response.json() == {
        "pendingIncomingRequests": 0,
        "unreadConnections": 0,
        "activityInvites": 0,
    }
    joined = " ".join(statements)
    for table in SOCIAL_TABLES:
        assert f"moodprint.{table}" not in joined, table


async def test_registered_cannot_select_guest_peer(clients):
    from app.infrastructure.database.models import Consent, User, now
    from app.modules.social.models import Connection, Pair, PublishedProfile

    app, actors = clients
    registered_client, registered_id = actors[0]
    await publish(registered_client)
    guest = await add_guest(app, consents=True)
    async with app.state.database.sessions.begin() as db:
        mine = await db.scalar(
            select(PublishedProfile).where(PublishedProfile.user_id == registered_id)
        )
        owner = await db.get(User, guest.user_id)
        owner.profile_version, owner.last_seen_at = 1, now()
        consent = await db.get(Consent, (guest.user_id, "MATCH"))
        # A forged but perfectly consistent published profile for the guest.
        db.add(
            PublishedProfile(
                user_id=guest.user_id,
                payload=mine.payload,
                version=1,
                consent_version=consent.version,
                valid=True,
            )
        )
        low, high = sorted((registered_id, guest.user_id))
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
        room = Connection(
            pair_id=pair.id,
            low_user_id=low,
            high_user_id=high,
            snapshots={
                str(registered_id): {"consent": 1},
                str(guest.user_id): {"consent": consent.version},
            },
        )
        db.add(room)
        await db.flush()
        room_id = room.id

    # Discovery, legacy room listing/detail/messaging and reveal/activity paths all stay closed.
    candidates = await registered_client.get("/api/v1/matching/candidates")
    assert candidates.status_code == 200 and candidates.json()["candidates"] == []
    listed = await registered_client.get("/api/v1/connections")
    assert listed.status_code == 200 and listed.json() == []
    for method, path, body in (
        ("GET", f"/api/v1/connections/{room_id}", None),
        ("GET", f"/api/v1/connections/{room_id}/messages", None),
        ("POST", f"/api/v1/connections/{room_id}/messages", {"clientMessageId": str(uuid4()), "text": "xin chào"}),
        ("POST", f"/api/v1/connections/{room_id}/peer-reference", {}),
        ("GET", f"/api/v1/connections/{room_id}/activities", None),
        ("GET", f"/api/v1/connections/{room_id}/reveal-requests", None),
    ):
        response = await registered_client.request(method, path, json=body, headers=key())
        assert response.status_code in (403, 404), (method, path, response.status_code)
        assert str(guest.user_id) not in response.text
        assert "xin chào" not in response.text
    from app.modules.social.models import HumanMessage

    async with app.state.database.sessions() as db:
        stored = (await db.scalars(select(HumanMessage))).all()
    assert stored == [], "a message must never be created in a room that includes a guest"


async def test_guest_cannot_read_other_guest(clients):
    app, _ = clients
    first = await add_guest(app)
    second = await add_guest(app)
    created = await first.client.post(
        "/api/v1/profiles/private-items", json={"text": "Điều riêng tư của khách A"}, headers=key()
    )
    assert created.status_code == 201, created.text
    item = created.json()["id"]
    for method, body in (
        ("PATCH", {"text": "bị sửa", "expectedVersion": 1}),
        ("DELETE", {"expectedVersion": 1}),
    ):
        response = await second.client.request(
            method, f"/api/v1/profiles/private-items/{item}", json=body, headers=key()
        )
        assert response.status_code == 404, (method, response.text)
        assert "Điều riêng tư" not in response.text
    listing = await second.client.get("/api/v1/profiles/private-items")
    assert listing.status_code == 200 and "Điều riêng tư" not in listing.text
    own = await first.client.get("/api/v1/profiles/private-items")
    assert "Điều riêng tư của khách A" in own.text


async def test_guest_cannot_read_registered_data(clients):
    app, actors = clients
    registered_client, _ = actors[0]
    created = await registered_client.post(
        "/api/v1/profiles/private-items", json={"text": "Canary người dùng chính thức"}, headers=key()
    )
    assert created.status_code == 201, created.text
    item = created.json()["id"]
    guest = await add_guest(app)
    for method, body in (
        ("PATCH", {"text": "ghi đè", "expectedVersion": 1}),
        ("DELETE", {"expectedVersion": 1}),
    ):
        response = await guest.client.request(
            method, f"/api/v1/profiles/private-items/{item}", json=body, headers=key()
        )
        assert response.status_code == 404
    assert "Canary" not in (await guest.client.get("/api/v1/profiles/private-items")).text
    still = await registered_client.get("/api/v1/profiles/private-items")
    assert "Canary người dùng chính thức" in still.text and "ghi đè" not in still.text


async def test_forged_staff_role_never_grants_a_guest(clients):
    from app.modules.moderation.models import StaffRole

    app, _ = clients
    app.state.settings.moderation_admin_enabled = True
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=guest.user_id, role="admin", granted_by="forged-test"))
    response = await guest.client.get("/api/v1/admin/reports")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REGISTERED_REQUIRED"
    assert (await guest.client.get("/api/v1/session")).json()["staff"] is None


async def test_activity_worker_aborts_a_forged_guest_session(clients):
    """A legacy/forged open activity that includes a guest is ended by the worker, not served."""
    from app.infrastructure.database.models import now
    from app.modules.activities.jobs import advance_due
    from app.modules.activities.models import ActivityParticipant, ActivitySession
    from app.modules.social.models import Connection, Pair

    app, actors = clients
    _, registered_id = actors[0]
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        low, high = sorted((registered_id, guest.user_id))
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
        room = Connection(pair_id=pair.id, low_user_id=low, high_user_id=high, snapshots={})
        db.add(room)
        await db.flush()
        session = ActivitySession(
            connection_id=room.id,
            pair_id=pair.id,
            kind="icebreaker",
            definition_version="icebreaker-v1",
            inviter_id=registered_id,
            invitee_id=guest.user_id,
            state="invited",
            deadline_at=now() + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        for user_id, role in ((registered_id, "inviter"), (guest.user_id, "invitee")):
            db.add(ActivityParticipant(session_id=session.id, user_id=user_id, role=role))
        session_id = session.id

    assert await advance_due(app, at=now() + timedelta(seconds=1)) >= 0
    async with app.state.database.sessions() as db:
        row = await db.get(ActivitySession, session_id)
    assert row.state == "aborted" and row.end_reason == "guest_participant"
