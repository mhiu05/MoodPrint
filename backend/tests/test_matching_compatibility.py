"""Every published taxonomy option must work in the rollback and shadow scorers."""

import pytest

from app.modules.matching import scoring, scoring_compat
from tests.social_helpers import consent, key, publish

EXTENDED = {
    "interests": ["chess", "anime", "podcasts"],
    "values": ["growth", "calm"],
    "style": "balanced",
    "goal": "study-buddy",
    "languages": ["vi"],
}


def test_rollback_keeps_the_frozen_formula_for_legacy_profiles():
    from itertools import combinations

    from tests.social_helpers import PROFILE

    for interests in combinations(scoring._INTERESTS, 3):
        for style in scoring._STYLES:
            peer = {**PROFILE, "interests": list(interests), "style": style}
            assert scoring_compat.score(PROFILE, peer) == scoring.score(
                scoring.v1_view(PROFILE), scoring.v1_view(peer)
            )


@pytest.mark.parametrize(
    "patch",
    [
        {"interests": ["unknown", "anime", "chess"]},
        {"goal": "unknown"},
        {"values": []},
        {"languages": ["unknown"]},
    ],
)
def test_rollback_rejects_unknown_or_incomplete_public_profiles(patch):
    assert scoring_compat.score(EXTENDED, {**EXTENDED, **patch}) == 0


@pytest.mark.parametrize("scorer", ["v1", "shadow", "v2"])
async def test_extended_profiles_can_discover_explain_invite_and_accept(clients, scorer):
    app, actors = clients
    app.state.settings.matching_scorer = scorer
    (one, _), (two, _) = actors
    for client in (one, two):
        await publish(client, EXTENDED)
    response = await one.get("/api/v1/matching/candidates")
    assert response.status_code == 200
    cards = response.json()["candidates"]
    assert len(cards) == 1
    assert cards[0]["scoringVersion"] == ("rules-v2" if scorer == "v2" else "rules-v1.1")
    assert any("cờ vua" in reason.lower() for reason in cards[0]["reasons"])
    sent = await one.post(
        "/api/v1/connection-requests",
        json={"candidateRef": cards[0]["candidateRef"]},
        headers={"Idempotency-Key": f"compat-{scorer}"},
    )
    assert sent.status_code == 201, sent.text
    incoming = (await two.get("/api/v1/connection-requests")).json()
    assert len(incoming) == 1
    accepted = await two.post(
        f"/api/v1/connection-requests/{incoming[0]['id']}/accept",
        json={"expectedVersion": incoming[0]["version"]},
        headers={"Idempotency-Key": f"accept-compat-{scorer}"},
    )
    assert accepted.status_code == 200, accepted.text
    assert len((await one.get("/api/v1/connections")).json()) == 1


async def test_concurrent_discovery_and_consent_withdrawal_never_leave_reusable_access(clients):
    import asyncio

    app, actors = clients
    (one, _), (two, _) = actors
    for client in (one, two):
        await publish(client, EXTENDED)
    before = (await one.get("/api/v1/matching/candidates")).json()["candidates"][0]
    results = await asyncio.gather(
        *[one.get("/api/v1/matching/candidates") for _ in range(8)],
        consent(two, False, 2),
    )
    assert all(result.status_code == 200 for result in results[:-1])
    assert (await one.get("/api/v1/matching/candidates")).json()["candidates"] == []
    refused = await one.post(
        "/api/v1/connection-requests", json={"candidateRef": before["candidateRef"]}, headers=key()
    )
    assert refused.status_code == 403
