"""T-MATCH-01/05: SQL eligibility (every exclusion rule), soft goals and the scorer flag."""

import logging
import re
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Consent, User, now
from app.modules.matching import scoring
from app.modules.social import retrieval
from app.modules.social.models import (
    Block,
    CandidateReference,
    Connection,
    ConnectionRequest,
    Pair,
    PublishedProfile,
)
from app.modules.social.service import pair_alias
from tests.social_helpers import PROFILE, publish

pytestmark = pytest.mark.postgres

PEER = {**PROFILE, "interests": ["reading", "music", "cooking"]}


async def seed_peer(app, profile=None, *, age="adult", consent=True, consent_version=1, **user):
    uid = uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(
            User(
                id=uid,
                auth_subject=uid,
                age_band=age,
                profile_version=1,
                last_seen_at=user.pop("last_seen_at", now()),
                **user,
            )
        )
        await db.flush()
        db.add(Consent(user_id=uid, purpose="MATCH", enabled=consent, version=consent_version))
        db.add(
            PublishedProfile(
                user_id=uid,
                payload={**PEER, **(profile or {})},
                version=1,
                consent_version=1,
                taxonomy_version="v2",
            )
        )
    return uid


async def candidate_aliases(client):
    response = await client.get("/api/v1/matching/candidates")
    assert response.status_code == 200, response.text
    return [card["alias"] for card in response.json()["candidates"]]


def use(app, scorer):
    app.state.settings.matching_scorer = scorer


async def viewer(clients, profile=None, scorer="v2"):
    app, actors = clients
    client, uid = actors[0]
    use(app, scorer)
    await publish(client, profile or PROFILE)
    return app, client, uid


async def pair_with(app, a: UUID, b: UUID, **fields):
    low, high = sorted((a, b))
    async with app.state.database.sessions.begin() as db:
        pair = Pair(low_user_id=low, high_user_id=high, **fields)
        db.add(pair)
        await db.flush()
        return pair.id, low, high


async def exclude(app, viewer_id, peer_id, rule):
    snapshots = {
        str(viewer_id): {"profile": 1, "consent": 1},
        str(peer_id): {"profile": 1, "consent": 1},
    }
    if rule in ("block_by_viewer", "blocked_by_peer"):
        blocker, blocked = (
            (viewer_id, peer_id) if rule == "block_by_viewer" else (peer_id, viewer_id)
        )
        async with app.state.database.sessions.begin() as db:
            db.add(Block(blocker_id=blocker, blocked_id=blocked))
    elif rule == "cooldown":
        await pair_with(app, viewer_id, peer_id, cooldown_until=now() + timedelta(days=3))
    elif rule == "open_room":
        pair_id, low, high = await pair_with(app, viewer_id, peer_id)
        async with app.state.database.sessions.begin() as db:
            db.add(
                Connection(pair_id=pair_id, low_user_id=low, high_user_id=high, snapshots=snapshots)
            )
    elif rule == "pending_request":
        pair_id, _, _ = await pair_with(app, viewer_id, peer_id)
        async with app.state.database.sessions.begin() as db:
            db.add(
                ConnectionRequest(
                    pair_id=pair_id,
                    sender_id=peer_id,
                    recipient_id=viewer_id,
                    snapshots=snapshots,
                    expires_at=now() + timedelta(days=7),
                )
            )


RULES = {
    "block_by_viewer": {},
    "blocked_by_peer": {},
    "cooldown": {},
    "open_room": {},
    "pending_request": {},
    "teen": {"age": "teen"},
    "match_off": {"consent": False},
    "stale_consent_version": {"consent_version": 2},
    "deletion_pending": {"deletion_pending": True},
    "inactive_31_days": {"last_seen_at": now() - timedelta(days=31)},
    "no_shared_language": {"profile": {"languages": ["en"]}},
    "peer_strict_goal": {"profile": {"goal": "study-buddy", "strict_goal": True}},
    "no_exact_shared_item": {
        "profile": {"interests": ["running", "chess", "anime"], "values": ["humor", "calm"]}
    },
}


@pytest.mark.parametrize("rule", sorted(RULES))
async def test_each_exclusion_rule_removes_the_peer(clients, rule):
    app, client, me = await viewer(clients)
    kept = await seed_peer(app)
    options = dict(RULES[rule])
    removed = await seed_peer(app, options.pop("profile", None), **options)
    await exclude(app, me, removed, rule)
    aliases = await candidate_aliases(client)
    assert pair_alias(me, kept)[0] in aliases
    assert pair_alias(me, removed)[0] not in aliases


async def test_withdrawn_and_old_profiles_are_hidden(clients):
    app, client, me = await viewer(clients)
    withdrawn, old = await seed_peer(app), await seed_peer(app)
    async with app.state.database.sessions.begin() as db:
        rows = (
            await db.scalars(
                select(PublishedProfile).where(PublishedProfile.user_id.in_([withdrawn, old]))
            )
        ).all()
        for row in rows:
            if row.user_id == withdrawn:
                row.valid = False
            else:
                row.created_at = now() - timedelta(days=181)
    assert await candidate_aliases(client) == []


async def test_unknown_last_seen_counts_as_active_until_the_cutoff(clients, monkeypatch):
    app, client, me = await viewer(clients)
    peer = await seed_peer(app, last_seen_at=None)
    assert pair_alias(me, peer)[0] in await candidate_aliases(client)
    monkeypatch.setattr(retrieval, "LAST_SEEN_ENFORCED_FROM", now() - timedelta(days=1))
    assert await candidate_aliases(client) == []


async def test_soft_goals_under_v2_and_hard_goals_under_v1(clients):
    app, client, me = await viewer(clients)
    peer = await seed_peer(app, {"goal": "study-buddy"})
    assert pair_alias(me, peer)[0] in await candidate_aliases(client)
    use(app, "v1")
    assert await candidate_aliases(client) == []


async def test_viewer_strict_goal_hides_other_goals(clients):
    app, client, me = await viewer(clients, {**PROFILE, "strictGoal": True})
    same = await seed_peer(app)
    other = await seed_peer(app, {"goal": "study-buddy"})
    aliases = await candidate_aliases(client)
    assert pair_alias(me, same)[0] in aliases and pair_alias(me, other)[0] not in aliases


async def test_v2_cards_and_references_record_the_scorer_and_rank(clients):
    app, client, me = await viewer(clients)
    for _ in range(3):
        await seed_peer(app)
    body = (await client.get("/api/v1/matching/candidates")).json()
    assert {card["scoringVersion"] for card in body["candidates"]} == {"rules-v2"}
    for card in body["candidates"]:
        assert card["matchLabel"] in ("many", "some") and card["sharedActivities"] == []
        assert 0 < len(card["reasons"]) <= 3
        assert not any(re.search(r"\d|%", reason) for reason in card["reasons"])
        assert "score" not in card
    async with app.state.database.sessions() as db:
        refs = (
            await db.scalars(select(CandidateReference).where(CandidateReference.user_id == me))
        ).all()
    assert sorted(ref.rank for ref in refs) == [0, 1, 2]
    assert {ref.scoring_version for ref in refs} == {"rules-v2"}


async def test_v1_keeps_the_original_order(clients):
    app, client, me = await viewer(clients, scorer="v1")
    profiles = [
        PROFILE,
        {**PROFILE, "values": ["respect", "kindness"]},
        {**PROFILE, "interests": ["reading", "music", "puzzles"]},
        {**PROFILE, "interests": ["reading", "english", "cooking"], "style": "direct"},
        {
            **PROFILE,
            "interests": ["reading", "photography", "puzzles"],
            "values": ["respect", "curiosity"],
        },
        {**PROFILE, "style": "listening"},
    ]
    peers = [await seed_peer(app, profile) for profile in profiles]
    own = scoring.v1_view(PROFILE)
    expected = sorted(
        (
            (scoring.score(own, scoring.v1_view({**PEER, **profile})), str(peer), peer)
            for profile, peer in zip(profiles, peers, strict=True)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    expected_aliases = [pair_alias(me, peer)[0] for points, _, peer in expected if points >= 30][:5]
    assert await candidate_aliases(client) == expected_aliases
    body = (await client.get("/api/v1/matching/candidates")).json()
    assert {card["scoringVersion"] for card in body["candidates"]} == {"rules-v1.1"}


async def test_shadow_serves_v1_and_logs_only_aggregates(clients, caplog):
    app, client, me = await viewer(clients, scorer="shadow")
    for _ in range(3):
        await seed_peer(app)
    with caplog.at_level(logging.INFO):
        body = (await client.get("/api/v1/matching/candidates")).json()
    assert {card["scoringVersion"] for card in body["candidates"]} == {"rules-v1.1"}
    lines = [
        record.getMessage() for record in caplog.records if "matching_shadow" in record.getMessage()
    ]
    assert len(lines) == 1
    assert re.fullmatch(
        r"matching_shadow overlap_at5=\d\.\d{2} v1_count=\d+ v2_count=\d+", lines[0]
    )
    assert str(me) not in lines[0]


async def test_fifty_peers_rank_quickly_with_bounded_queries(clients):
    import time

    app, client, me = await viewer(clients)
    for _ in range(50):
        await seed_peer(app)
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        assert len(await candidate_aliases(client)) == 5
        timings.append(time.perf_counter() - start)
    assert sorted(timings)[-1] < 0.6
