"""Readiness requires the schema needed to enforce the privacy projection."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("revision", "status"),
    [
        ("0010_account_deletion", 503),
        ("0011_social_stabilization", 503),
        ("0012_matching_v2", 503),
        ("0013_shared_activities", 503),
        ("0014_moderation", 503),
        ("0015_context_privacy", 503),
        ("0016_guest_foundation", 503),
        ("0017_guest_security", 503),
        ("0018_app_feedback", 503),
        ("0019_journal", 503),
        ("0020_private_profile_retirement", 503),
        ("0021_multi_message", 503),
        ("0022_proactive_messages", 503),
        ("0023_collaboration", 200),
        ("0017_unreviewed", 503),
        ("9999_unknown", 503),
    ],
)
async def test_readiness_accepts_only_reviewed_window_revisions(clients, revision, status):
    from app.core.revisions import READY_REVISIONS

    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text(
                "create table if not exists moodprint.alembic_version"
                " (version_num varchar(32) primary key)"
            )
        )
        await db.execute(text("delete from moodprint.alembic_version"))
        await db.execute(text("insert into moodprint.alembic_version values (:v)"), {"v": revision})
    response = await actors[0][0].get("/api/v1/health/ready")
    assert response.status_code == status
    assert (revision in READY_REVISIONS) == (status == 200)
