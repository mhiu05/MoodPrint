"""Discovery v1 contract: public metadata is additive; canonical matching is unchanged."""

import copy

import pytest
from pydantic import ValidationError

from app.modules.social.schemas import DraftInput, PublicProfile
from app.modules.social.service import public_payload, validate_publishable
from tests.social_helpers import PROFILE

DISCOVERY = {
    "version": 1,
    "intention": "experiences",
    "connectionApproach": "activity-first",
    "featuredInterests": ["music", "reading"],
}


def test_legacy_profile_and_partial_discovery_round_trip():
    assert PublicProfile.model_validate(PROFILE).model_dump().get("discovery") is None
    profile = PublicProfile.model_validate({**PROFILE, "discovery": DISCOVERY})
    assert profile.model_dump(by_alias=True)["discovery"] == DISCOVERY
    assert profile.model_dump()["discovery"]["connection_approach"] == "activity-first"
    partial = PublicProfile.model_validate({"discovery": {"version": 1}})
    assert partial.model_dump(by_alias=True)["discovery"] == {
        "version": 1,
        "intention": None,
        "connectionApproach": None,
        "featuredInterests": [],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"version": 2},
        {"intention": "dating"},
        {"connectionApproach": "direct"},
        {"featuredInterests": ["music", "music"]},
        {"featuredInterests": ["sports"]},
        {"featuredInterests": ["coffee", "reading", "music", "walking"]},
        {"featuredInterests": ["coffee"]},
        {"privateIdentity": "secret"},
    ],
)
def test_invalid_explicit_discovery_is_rejected(change):
    with pytest.raises(ValidationError):
        PublicProfile.model_validate({**PROFILE, "discovery": {**DISCOVERY, **change}})


def test_older_writer_preserves_and_intersects_metadata_without_mutating_source():
    source = PublicProfile.model_validate({**PROFILE, "discovery": DISCOVERY}).model_dump()
    before = copy.deepcopy(source)
    body = DraftInput.model_validate(
        {**PROFILE, "interests": ["reading", "coffee"], "expectedVersion": 2}
    )
    saved = public_payload(body, previous=source)
    assert saved["interests"] == ["reading", "coffee"]
    assert saved["discovery"]["featured_interests"] == ["reading"]
    assert saved["discovery"]["intention"] == "experiences"
    assert source == before
    # Full PUT still clears omitted canonical optional facets.
    assert saved["activities"] == []


def test_explicit_null_clears_extension_and_explicit_metadata_replaces():
    source = PublicProfile.model_validate({**PROFILE, "discovery": DISCOVERY}).model_dump()
    body = DraftInput.model_validate({**PROFILE, "discovery": None, "expectedVersion": 1})
    assert public_payload(body, previous=source)["discovery"] is None
    body = DraftInput.model_validate({**PROFILE, "discovery": {"version": 1}, "expectedVersion": 1})
    assert public_payload(body, previous=source)["discovery"]["featured_interests"] == []


def test_metadata_does_not_relax_canonical_publish_minimums():
    validate_publishable(
        PublicProfile.model_validate({**PROFILE, "discovery": DISCOVERY}).model_dump()
    )
    from app.core.errors import DomainError

    for facet, ids in [
        ("interests", ["music", "reading"]),
        ("values", ["respect"]),
        ("languages", []),
    ]:
        with pytest.raises(DomainError) as failure:
            validate_publishable({**PROFILE, facet: ids})
        assert failure.value.code == "PROFILE_INCOMPLETE"


@pytest.mark.parametrize("scorer", ["v1", "v2", "shadow"])
def test_metadata_cannot_change_matching_scores_explanations_or_eligibility(scorer):
    from app.modules.matching import scoring_compat, scoring_v2
    from app.modules.social.service import describe, goals_compatible, suggestible

    canonical = PublicProfile.model_validate(PROFILE).model_dump()
    extended = PublicProfile.model_validate({**PROFILE, "discovery": DISCOVERY}).model_dump()
    other = {**canonical, "style": "listening"}
    assert scoring_compat.score(canonical, other) == scoring_compat.score(extended, other)
    assert scoring_v2.score(canonical, other) == scoring_v2.score(extended, other)
    assert describe(canonical, other, scorer) == describe(extended, other, scorer)
    assert goals_compatible(canonical, other, scorer) == goals_compatible(extended, other, scorer)
    assert suggestible(canonical, other, scorer) == suggestible(extended, other, scorer)


@pytest.mark.postgres
async def test_api_older_writer_round_trip_and_consent(clients):
    from tests.social_helpers import key

    _, actors = clients
    client = actors[0][0]
    path = "/api/v1/profiles/matching-draft"
    saved = await client.put(
        path, json={**PROFILE, "discovery": DISCOVERY, "expectedVersion": 0}, headers=key()
    )
    assert saved.status_code == 200, saved.text
    older = await client.put(path, json={**PROFILE, "expectedVersion": 1}, headers=key())
    assert older.status_code == 200, older.text
    assert older.json()["profile"]["discovery"] == DISCOVERY
    preview = await client.post(path + "/preview")
    assert preview.status_code == 200
    assert preview.json()["profile"]["discovery"] == DISCOVERY
    assert (await client.get("/api/v1/session")).json()["consents"]["MATCH"]["enabled"] is False


@pytest.mark.postgres
async def test_incomplete_discovery_is_private_durable_and_owner_scoped(clients):
    from sqlalchemy import select

    from app.modules.social.models import MatchingDraft, PublishedProfile
    from tests.social_helpers import key

    app, actors = clients
    own, other = actors[0][0], actors[1][0]
    path = "/api/v1/profiles/matching-draft"
    body = {
        "interests": ["music"],
        "discovery": {
            "version": 1,
            "intention": "study",
            "featuredInterests": ["music"],
        },
        "expectedVersion": 0,
    }
    saved = await own.put(path, json=body, headers=key())
    assert saved.status_code == 200, saved.text
    assert (await own.get(path)).json() == saved.json()
    assert (await other.get(path)).json()["version"] == 0
    assert (await other.get(path)).json()["profile"]["interests"] == []
    assert (await own.post(path + "/preview")).status_code == 422
    assert (await own.get("/api/v1/profiles/published/current")).json() is None
    assert not (await own.get("/api/v1/session")).json()["consents"]["MATCH"]["enabled"]
    # Ownership is session-bound, never a submitted user id.
    foreign = await other.put(path, json={**body, "userId": str(actors[0][1])}, headers=key())
    assert foreign.status_code == 422
    async with app.state.database.sessions() as db:
        draft = await db.get(MatchingDraft, actors[0][1])
        assert draft.payload["discovery"]["intention"] == "study"
        assert draft.payload["interests"] == ["music"]
        assert await db.get(MatchingDraft, actors[1][1]) is None
        assert (await db.scalars(select(PublishedProfile))).all() == []


@pytest.mark.postgres
async def test_full_interest_rollback_omission_null_and_receipt_presence_persist(clients):
    from app.modules.social.models import MatchingDraft
    from tests.social_helpers import key

    app, actors = clients
    client = actors[0][0]
    path = "/api/v1/profiles/matching-draft"
    interests = [
        "reading",
        "music",
        "coffee",
        "walking",
        "running",
        "cycling",
        "yoga",
        "football",
        "badminton",
        "drawing",
    ]
    canonical = {
        **PROFILE,
        "interests": interests,
        "goal": "language-practice",
        "style": "direct",
        "strictGoal": True,
        "languages": ["vi", "en"],
        "activities": ["focus"],
        "availability": ["weekday_evening"],
    }
    current = await client.put(
        path, json={**canonical, "discovery": DISCOVERY, "expectedVersion": 0}, headers=key()
    )
    assert current.status_code == 200, current.text
    headers = key()
    old_body = {**canonical, "expectedVersion": 1}
    older = await client.put(path, json=old_body, headers=headers)
    assert older.status_code == 200, older.text
    assert older.json()["profile"]["discovery"] == DISCOVERY
    assert older.json()["profile"]["interests"] == interests
    assert older.json()["profile"]["goal"] == "language-practice"
    replay = await client.put(path, json=old_body, headers=headers)
    assert replay.json() == older.json()
    # Omission and explicit null must not share an idempotency receipt.
    conflict = await client.put(path, json={**old_body, "discovery": None}, headers=headers)
    assert conflict.status_code == 409
    removed = await client.put(
        path, json={**canonical, "interests": interests[1:], "expectedVersion": 2}, headers=key()
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["profile"]["discovery"]["featuredInterests"] == ["music"]
    cleared = await client.put(
        path, json={**canonical, "discovery": None, "expectedVersion": 3}, headers=key()
    )
    assert cleared.status_code == 200, cleared.text
    restored = (await client.get(path)).json()
    assert restored["profile"]["discovery"] is None
    assert restored["profile"]["interests"] == interests
    async with app.state.database.sessions() as db:
        persisted = await db.get(MatchingDraft, actors[0][1])
        assert persisted.payload["discovery"] is None
        assert persisted.payload["interests"] == interests
        assert persisted.version == 4


@pytest.mark.postgres
async def test_concurrent_discovery_saves_and_expired_preview_cannot_publish(clients):
    import asyncio
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.infrastructure.database.models import ConsentEvent, now
    from app.modules.social.models import MatchingDraft, PublishedProfile
    from tests.social_helpers import key

    app, actors = clients
    client = actors[0][0]
    path = "/api/v1/profiles/matching-draft"
    responses = await asyncio.gather(
        *[
            client.put(
                path,
                json={
                    **PROFILE,
                    "discovery": {**DISCOVERY, "intention": intention},
                    "expectedVersion": 0,
                },
                headers=key(),
            )
            for intention in ("talk", "study")
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    preview = (await client.post(path + "/preview")).json()
    async with app.state.database.sessions.begin() as db:
        draft = await db.get(MatchingDraft, actors[0][1])
        assert draft.version == 1
        draft.preview_expires_at = now() - timedelta(seconds=1)
    rejected = await client.post(
        "/api/v1/profiles/published",
        json={
            "draftVersion": preview["draftVersion"],
            "previewDigest": preview["previewDigest"],
            "expectedPublishedVersion": 0,
        },
        headers=key(),
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "PREVIEW_CHANGED"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(PublishedProfile)) == 0
        assert await db.scalar(select(func.count()).select_from(ConsentEvent)) == 0


@pytest.mark.postgres
async def test_first_legacy_draft_preserves_published_discovery_and_publish_retry(clients):
    from sqlalchemy import delete, func, select

    from app.infrastructure.database.models import ConsentEvent
    from app.modules.social.models import MatchingDraft, PublishedProfile
    from tests.social_helpers import key

    app, actors = clients
    client = actors[0][0]
    path = "/api/v1/profiles/matching-draft"
    saved = await client.put(
        path, json={**PROFILE, "discovery": DISCOVERY, "expectedVersion": 0}, headers=key()
    )
    assert saved.status_code == 200
    preview = (await client.post(path + "/preview")).json()
    headers = key()
    body = {
        "draftVersion": preview["draftVersion"],
        "previewDigest": preview["previewDigest"],
        "expectedPublishedVersion": 0,
    }
    first = await client.post("/api/v1/profiles/published", json=body, headers=headers)
    retry = await client.post("/api/v1/profiles/published", json=body, headers=headers)
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    async with app.state.database.sessions.begin() as db:
        assert await db.scalar(select(func.count()).select_from(PublishedProfile)) == 1
        assert await db.scalar(select(func.count()).select_from(ConsentEvent)) == 1
        await db.execute(delete(MatchingDraft).where(MatchingDraft.user_id == actors[0][1]))
    legacy = await client.put(path, json={**PROFILE, "expectedVersion": 0}, headers=key())
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["profile"]["discovery"] == DISCOVERY
    assert (await client.get("/api/v1/profiles/published/current")).json() == first.json()
