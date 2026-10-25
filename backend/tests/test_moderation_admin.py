"""T-MOD-01: staff-only queue, claim/resolve compare-and-set, audit rows, no identities."""

import importlib.util
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.infrastructure.database.models import AuthSession, now
from app.modules.moderation.models import ModerationAction, Report, StaffRole
from tests.conftest import add_actor
from tests.social_helpers import key, open_room

pytestmark = pytest.mark.postgres


async def reported(clients):
    """A reports B with one selected message; C is the moderator."""
    app, actors, _, room = await open_room(clients)
    (a, a_id), (b, b_id) = actors
    message = (
        await b.post(
            f"/api/v1/connections/{room}/messages",
            json={"text": "Tin nhắn quấy rối", "clientMessageId": str(uuid4())},
            headers=key(),
        )
    ).json()
    ref = (
        await a.post(f"/api/v1/connections/{room}/peer-reference", json={}, headers=key())
    ).json()["peerRef"]
    created = await a.post(
        "/api/v1/reports",
        json={"peerRef": ref, "reason": "Quấy rối", "selectedMessageIds": [message["id"]]},
        headers=key(),
    )
    assert created.status_code == 201, created.text
    staff, staff_id = await add_actor(app, 9)
    app.state.settings.moderation_admin_enabled = True
    return app, a, b, b_id, staff, staff_id, created.json()["id"]


async def grant(app, uid, role="moderator"):
    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=uid, role=role, granted_by="test"))


async def test_flag_off_hides_the_routes_and_non_staff_are_refused(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    app.state.settings.moderation_admin_enabled = False
    assert (await staff.get("/api/v1/admin/reports")).status_code == 404
    app.state.settings.moderation_admin_enabled = True
    denied = await a.get("/api/v1/admin/reports")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "STAFF_REQUIRED"
    session = (await a.get("/api/v1/session")).json()
    assert session["staff"] is None


async def test_queue_shows_evidence_but_no_identities(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    assert (await staff.get("/api/v1/session")).json()["staff"] == "moderator"
    response = await staff.get("/api/v1/admin/reports")
    assert response.status_code == 200, response.text
    [row] = response.json()
    assert row["status"] == "received" and row["reason"] == "Quấy rối"
    assert row["evidence"] == [{"kind": "message", "text": "Tin nhắn quấy rối"}]
    assert str(b_id) not in response.text and "@" not in response.text
    assert row["subjectRef"].startswith("s-") and row["priorActions"] == 0


async def test_claim_and_resolve_are_compare_and_set_and_audited(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    claimed = await staff.post(
        f"/api/v1/admin/reports/{report_id}/claim", json={"expectedVersion": 1}, headers=key()
    )
    assert claimed.status_code == 200 and claimed.json()["status"] == "in_review"
    stale = await staff.post(
        f"/api/v1/admin/reports/{report_id}/claim", json={"expectedVersion": 1}, headers=key()
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REPORT_CHANGED"
    resolved = await staff.post(
        f"/api/v1/admin/reports/{report_id}/resolve",
        json={"expectedVersion": 2, "action": "warn", "note": "Nhắc nhở lần đầu"},
        headers=key(),
    )
    assert resolved.status_code == 200, resolved.text
    assert (resolved.json()["status"], resolved.json()["resolution"]) == ("resolved", "warned")
    async with app.state.database.sessions() as db:
        actions = (await db.scalars(select(ModerationAction))).all()
        row = await db.get(Report, resolved.json()["id"])
    assert [(x.action, x.subject_id, x.staff_id) for x in actions] == [("warn", b_id, staff_id)]
    assert row.reviewed_at is not None
    status = (await a.get(f"/api/v1/reports/{report_id}")).json()
    assert status["status"] == "resolved"
    notices = (await b.get("/api/v1/session")).json()["notices"]
    assert notices == [{"kind": "warning", "until": None}]


async def test_restrict_needs_days_and_staff_must_have_reauthenticated(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    missing_days = await staff.post(
        f"/api/v1/admin/reports/{report_id}/resolve",
        json={"expectedVersion": 1, "action": "restrict"},
        headers=key(),
    )
    assert missing_days.status_code == 422
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == staff_id)
            .values(reauthenticated_at=now() - timedelta(hours=13))
        )
    stale = await staff.get("/api/v1/admin/reports")
    assert stale.status_code == 403 and stale.json()["error"]["code"] == "REAUTH_REQUIRED"


async def test_only_admins_lift(clients):
    app, a, b, b_id, staff, staff_id, report_id = await reported(clients)
    await grant(app, staff_id)
    row = (await staff.get("/api/v1/admin/reports")).json()[0]
    lifted = await staff.post(
        f"/api/v1/admin/users/{row['subjectRef']}/lift", json={"note": ""}, headers=key()
    )
    assert lifted.status_code == 403
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(StaffRole).values(role="admin"))
    lifted = await staff.post(
        f"/api/v1/admin/users/{row['subjectRef']}/lift",
        json={"note": "Kháng nghị hợp lệ"},
        headers=key(),
    )
    assert lifted.status_code == 200, lifted.text


def test_grant_script_refuses_hosted_databases():
    path = Path(__file__).resolve().parents[2] / "scripts/grant_staff_role.py"
    spec = importlib.util.spec_from_file_location("grant_staff_role", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):
        module.local_url("postgresql://u:p@db.example.supabase.co:5432/postgres")
    assert module.local_url("postgresql://u:p@127.0.0.1:16432/x_test")
