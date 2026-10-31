"""An operator role and recent reauthentication cannot override global adult policy."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.infrastructure.database.models import AgeDeclaration, AuthSession, User, now
from app.modules.moderation.models import ModerationAction, Report, StaffRole
from tests.social_helpers import key

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("condition", ["teen", "unknown", "missing-declaration"])
@pytest.mark.parametrize(
    "operation",
    ["queue", "claim", "resolve", "lift", "feedback-list", "feedback-summary", "feedback-review"],
)
async def test_staff_role_and_recent_reauth_do_not_bypass_adult_eligibility(
    clients, condition, operation
):
    app, actors = clients
    client, staff_id = actors[0]
    subject_id = actors[1][1]
    report_id = uuid4()
    app.state.settings.moderation_admin_enabled = True
    app.state.settings.feedback_admin_enabled = True
    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=staff_id, role="admin", granted_by="synthetic"))
        user = await db.get(User, staff_id)
        if condition == "missing-declaration":
            await db.delete(await db.get(AgeDeclaration, staff_id))
        else:
            user.age_band = condition
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == staff_id))
        session.reauthenticated_at = now()
        subject = await db.get(User, subject_id)
        subject.social_restricted_until = now() + timedelta(days=1)
        db.add(Report(
            id=report_id, reporter_id=staff_id, subject_id=subject_id,
            reason="Synthetic report", evidence=[{"kind": "message", "text": "PRIVATE_STAFF_EVIDENCE"}],
        ))
    base = f"/api/v1/admin/reports/{report_id}"
    if operation == "queue":
        response = await client.get("/api/v1/admin/reports")
    elif operation == "claim":
        response = await client.post(f"{base}/claim", json={"expectedVersion": 1}, headers=key())
    elif operation == "resolve":
        response = await client.post(
            f"{base}/resolve", json={"expectedVersion": 1, "action": "warn", "note": ""}, headers=key()
        )
    elif operation == "lift":
        response = await client.post(
            f"/api/v1/admin/users/s-{report_id.hex}/lift", json={"note": ""}, headers=key()
        )
    elif operation == "feedback-list":
        response = await client.get("/api/v1/admin/feedback")
    elif operation == "feedback-summary":
        response = await client.get("/api/v1/admin/feedback/summary")
    else:
        response = await client.patch(
            f"/api/v1/admin/feedback/{uuid4()}",
            json={"status": "reviewed", "expectedVersion": 1}, headers=key(),
        )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "ELIGIBILITY_REQUIRED"
    assert "PRIVATE_STAFF_EVIDENCE" not in response.text
    async with app.state.database.sessions() as db:
        row = await db.get(Report, report_id)
        assert (row.status, row.version) == ("received", 1)
        assert await db.scalar(select(func.count()).select_from(ModerationAction)) == 0
        assert (await db.get(User, subject_id)).social_restricted_until is not None
