import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import User
from tests.social_helpers import key

pytestmark = pytest.mark.postgres
YEAR = datetime.now(ZoneInfo("Asia/Bangkok")).year
PATH = "/api/v1/users/me/eligibility"


def declaration(years=16, **changes):
    return {
        "birthYear": YEAR - years,
        "confirmedMinimumAge": True,
        "confirmedAdultAge": False,
        "expectedVersion": 0,
        "policyVersion": "self-declared-age-v1",
        **changes,
    }


async def unknown(clients):
    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        for _, uid in actors:
            (await db.get(User, uid)).age_band = "unknown"
    return app, actors


async def test_sixteen_year_attestation_unlocks_personal_features_without_consents_or_social(
    clients,
):
    _, actors = await unknown(clients)
    a, _ = actors[0]
    headers = key()
    response = await a.put(PATH, json=declaration(), headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["eligible"] and result["ageBand"] == "teen" and result["eligibilityVersion"] == 1
    assert result["birthYear"] == YEAR - 16
    assert all(result["consents"][purpose]["enabled"] for purpose in ("AI", "MEM", "VOICE"))
    assert result["consents"]["MATCH"]["enabled"] is False
    assert (await a.get("/api/v1/matching/candidates")).status_code == 403
    assert (
        await a.put(
            "/api/v1/consents/MATCH",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
            headers=key(),
        )
    ).status_code == 403
    replay = await a.put(PATH, json=declaration(), headers=headers)
    assert replay.status_code == 200 and replay.json()["eligibilityVersion"] == 1
    other = (await actors[1][0].get("/api/v1/session")).json()
    assert other["ageBand"] == "unknown" and other["birthYear"] is None


async def test_eighteenth_year_requires_explicit_adult_confirmation_then_can_upgrade(clients):
    _, actors = await unknown(clients)
    a, _ = actors[0]
    initial = await a.put(PATH, json=declaration(18), headers=key())
    assert initial.status_code == 200 and initial.json()["ageBand"] == "teen"
    confirmed = await a.put(
        PATH, json=declaration(18, confirmedAdultAge=True, expectedVersion=1), headers=key()
    )
    assert confirmed.status_code == 200 and confirmed.json()["ageBand"] == "adult"
    assert confirmed.json()["eligibilityVersion"] == 2
    assert not confirmed.json()["consents"]["MATCH"]["enabled"]
    older = await actors[1][0].put(PATH, json=declaration(19), headers=key())
    assert older.status_code == 200 and older.json()["ageBand"] == "adult"


async def test_under_sixteen_cannot_open_features_or_retry_with_an_older_birth_year(clients):
    _, actors = await unknown(clients)
    a, _ = actors[0]
    result = await a.put(PATH, json=declaration(15), headers=key())
    assert result.status_code == 200
    assert not result.json()["eligible"] and result.json()["ageBand"] == "under16"
    assert (await a.get("/api/v1/moods")).status_code == 403
    retry = await a.put(
        PATH, json=declaration(25, expectedVersion=1, confirmedAdultAge=True), headers=key()
    )
    assert retry.status_code == 409


async def test_forged_age_fields_future_year_and_false_confirmations_fail_before_persistence(
    clients,
):
    _, actors = await unknown(clients)
    a, _ = actors[0]
    for changes in (
        {"ageBand": "adult"},
        {"userId": str(actors[1][1])},
        {"birthYear": YEAR + 1},
        {"birthYear": "2000"},
        {"birthYear": 1899},
        {"confirmedMinimumAge": False},
        {"confirmedMinimumAge": 1},
        {"confirmedAdultAge": True},
    ):
        response = await a.put(PATH, json=declaration(**changes), headers=key())
        assert response.status_code == 422, response.text
    assert (await a.get("/api/v1/session")).json()["ageBand"] == "unknown"
    no_csrf = await a.put(PATH, json=declaration(), headers={**key(), "X-CSRF-Token": ""})
    assert no_csrf.status_code == 403


async def test_concurrent_declarations_have_one_versioned_result(clients):
    from app.infrastructure.database.models import AgeDeclaration

    app, actors = await unknown(clients)
    a, uid = actors[0]
    results = await asyncio.gather(
        *[a.put(PATH, json=declaration(years), headers=key()) for years in (16, 19)]
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    async with app.state.database.sessions() as db:
        records = (
            await db.scalars(select(AgeDeclaration).where(AgeDeclaration.user_id == uid))
        ).all()
        assert len(records) == 1 and records[0].version == 1


async def test_birth_year_is_owner_private_and_can_be_exported_explicitly(clients):
    _, actors = await unknown(clients)
    for index, (client, _) in enumerate(actors):
        assert (
            await client.put(PATH, json=declaration(20 + index), headers=key())
        ).status_code == 200
    for index, (client, _) in enumerate(actors):
        created = await client.post("/api/v1/exports", json={"scopes": ["account"]}, headers=key())
        assert created.status_code == 201
        downloaded = await client.get(f"/api/v1/exports/{created.json()['id']}/download")
        assert downloaded.json()["account"]["birthYear"] == YEAR - 20 - index
        assert "moods" not in downloaded.json()
