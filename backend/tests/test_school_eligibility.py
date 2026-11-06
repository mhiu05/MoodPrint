"""Four eligibility combinations: profile and the school row, not a global switch."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.auth.age import AGE_REQUIRED_MESSAGE
from app.modules.school.eligibility import SCHOOL_REQUIRED_MESSAGE
from app.modules.school.models import SchoolProfile
from tests.conftest import add_actor

pytestmark = pytest.mark.postgres


@pytest.fixture
async def school_app(database):
    from app.core.config import Settings
    from app.main import create_app
    from tests.settings_baseline import ALL_FEATURES_OFF

    app = create_app(Settings(
        _env_file=None,
        app_profile="school_safety",
        database_url=str(database.url.render_as_string(hide_password=False)),
        **ALL_FEATURES_OFF,
    ))
    await app.state.database.engine.dispose()
    app.state.database.engine = database
    app.state.database.sessions = async_sessionmaker(
        database, expire_on_commit=False, info={"app_profile": "school_safety"}
    )
    app.state.test_clients = []
    yield app
    for client in app.state.test_clients:
        await client.aclose()
    await app.state.ai.close()


async def moods(client):
    response = await client.get("/api/v1/moods")
    return response.status_code, response.json()


async def test_eligibility_follows_profile_and_the_school_row(clients, school_app):
    app, actors = clients
    adult, _ = actors[0]
    status, body = await moods(adult)
    assert status == 200 and body == []

    teen, teen_id = await add_actor(app, 8, age_band="teen")
    async with app.state.database.sessions.begin() as db:
        db.add(SchoolProfile(
            user_id=teen_id,
            age_group="15-17",
            terms_version="school-terms-v1",
            terms_accepted_at=datetime.now(UTC),
        ))
    status, body = await moods(teen)
    assert status == 403
    assert body["error"]["code"] == "ELIGIBILITY_REQUIRED"
    assert body["error"]["message"] == AGE_REQUIRED_MESSAGE

    school_adult, _ = await add_actor(school_app, 9, age_band="adult")
    status, body = await moods(school_adult)
    assert status == 403
    assert body["error"]["code"] == "ELIGIBILITY_REQUIRED"
    assert body["error"]["message"] == SCHOOL_REQUIRED_MESSAGE

    student, student_id = await add_actor(school_app, 10, age_band="teen")
    async with school_app.state.database.sessions.begin() as db:
        db.add(SchoolProfile(user_id=student_id, age_group="11-14"))
    status, body = await moods(student)
    assert status == 403 and body["error"]["message"] == SCHOOL_REQUIRED_MESSAGE
    async with school_app.state.database.sessions.begin() as db:
        profile = await db.get(SchoolProfile, student_id)
        profile.terms_version = "school-terms-v1"
        profile.terms_accepted_at = datetime.now(UTC)
    status, body = await moods(student)
    assert status == 200 and body == []
    session = (await student.get("/api/v1/session")).json()
    assert session["eligible"] is True
