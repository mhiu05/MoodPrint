"""Profile v2: new optional facets, per-facet limits and backward-compatible v1 payloads."""

import pytest
from sqlalchemy import select

from app.modules.matching import scoring
from app.modules.social.models import PublishedProfile
from tests.social_helpers import PROFILE, consent, key, publish

pytestmark = pytest.mark.postgres

V2 = {
    **PROFILE,
    "interests": ["reading", "coffee", "boardgames", "running"],
    "values": ["curiosity", "humor"],
    "goal": "study-buddy",
    "activities": ["focus", "coop_quiz"],
    "availability": ["weekday_evening", "weekend_morning"],
    "strictGoal": True,
}


async def save_draft(client, profile, expected=0):
    return await client.put(
        "/api/v1/profiles/matching-draft",
        json={**profile, "expectedVersion": expected},
        headers=key(),
    )


async def test_v2_profile_publishes_with_new_facets_and_version(clients):
    app, actors = clients
    client, uid = actors[0]
    published = await publish(client, V2)
    assert published["profile"]["activities"] == ["focus", "coop_quiz"]
    assert published["profile"]["availability"] == ["weekday_evening", "weekend_morning"]
    assert published["profile"]["strictGoal"] is True
    current = (await client.get("/api/v1/profiles/published/current")).json()
    assert current["profile"] == published["profile"]
    async with app.state.database.sessions() as db:
        row = await db.scalar(select(PublishedProfile).where(PublishedProfile.user_id == uid))
    assert row.taxonomy_version == "v2"
    assert row.payload["strict_goal"] is True


async def test_v1_shaped_profile_still_publishes(clients):
    _, actors = clients
    published = await publish(actors[0][0], PROFILE)
    assert published["profile"]["activities"] == []
    assert published["profile"]["availability"] == []
    assert published["profile"]["strictGoal"] is False


@pytest.mark.parametrize(
    "change",
    [
        {
            "interests": [
                *V2["interests"],
                "music",
                "walking",
                "cooking",
                "travel",
                "plants",
                "chess",
                "yoga",
            ]
        },
        {"values": ["curiosity", "humor", "calm", "growth", "kindness"]},
        {"activities": ["focus", "karaoke"]},
        {"availability": ["midnight"]},
        {"activities": ["focus", "focus"]},
        {"goal": "dating"},
    ],
)
async def test_out_of_range_or_unknown_facets_are_rejected(clients, change):
    _, actors = clients
    await consent(actors[0][0])
    response = await save_draft(actors[0][0], {**V2, **change})
    assert response.status_code == 422, response.text


async def test_publish_enforces_minimums(clients):
    _, actors = clients
    client = actors[0][0]
    await consent(client)
    assert (await save_draft(client, {**V2, "interests": ["reading", "coffee"]})).status_code == 200
    response = await client.post("/api/v1/profiles/matching-draft/preview")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROFILE_INCOMPLETE"


def test_v1_scorer_ignores_v2_only_fields():
    core = {**PROFILE, "sources": []}
    with_v2 = scoring.v1_view(
        {**PROFILE, "activities": ["focus"], "availability": [], "strict_goal": True}
    )
    assert with_v2 == core
    assert scoring.score(with_v2, scoring.v1_view(PROFILE)) == scoring.score(core, core)
