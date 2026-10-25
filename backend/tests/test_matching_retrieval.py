from uuid import uuid4

import pytest
from sqlalchemy import event

from app.infrastructure.database.models import Consent, User
from app.modules.social.models import PublishedProfile
from tests.social_helpers import PROFILE, publish

pytestmark = pytest.mark.postgres


async def test_matching_scores_all_eligible_profiles_without_per_candidate_sql_queries(clients):
    app, actors = clients
    await publish(actors[0][0])
    identities = sorted(uuid4() for _ in range(50))
    async with app.state.database.sessions.begin() as db:
        for uid in identities:
            db.add(User(id=uid, auth_subject=uid, age_band="adult", profile_version=1))
        await db.flush()
        for uid in identities:
            db.add(Consent(user_id=uid, purpose="MATCH", enabled=True, version=1))
            db.add(PublishedProfile(user_id=uid, payload=PROFILE, version=1, consent_version=1))
    queries = []

    def observed(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(app.state.database.engine.sync_engine, "before_cursor_execute", observed)
    try:
        response = await actors[0][0].get("/api/v1/matching/candidates")
    finally:
        event.remove(app.state.database.engine.sync_engine, "before_cursor_execute", observed)
    assert response.status_code == 200, response.text
    assert len(response.json()["candidates"]) == 5
    assert len(queries) <= 40, (
        f"Candidate retrieval made {len(queries)} SQL statements for 50 profiles"
    )
