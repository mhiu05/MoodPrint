"""DR-16: readiness accepts a short list of schema heads so an app rollback stays ready."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("revision", "status"),
    [
        ("0010_account_deletion", 200),
        ("0011_social_stabilization", 200),
        ("0009_memory_embeddings", 503),
        ("9999_unknown", 503),
    ],
)
async def test_readiness_accepts_only_listed_revisions(clients, revision, status):
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
