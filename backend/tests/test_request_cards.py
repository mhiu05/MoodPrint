"""DR-07: a pending request shows the counterpart's public card, never private data."""

import pytest

from app.modules.social.service import pair_alias
from tests.conftest import add_actor
from tests.social_helpers import PROFILE, key, publish, published_pair, republish

pytestmark = pytest.mark.postgres

OTHER = {**PROFILE, "interests": ["reading", "music", "cooking"], "values": ["respect", "kindness"]}


async def test_pending_requests_carry_the_counterpart_card_for_both_sides(clients):
    app, actors, _ = await published_pair(clients)
    (a, a_id), (b, b_id) = actors
    # Republish B with different tags so each side must see the *other* profile.
    await republish(b, OTHER)
    ref = (await a.get("/api/v1/matching/candidates")).json()["candidates"][0]["candidateRef"]
    sent = await a.post("/api/v1/connection-requests", json={"candidateRef": ref}, headers=key())
    assert sent.status_code == 201, sent.text
    alias, seed = pair_alias(a_id, b_id)
    outgoing = (await a.get("/api/v1/connection-requests")).json()[0]
    incoming = (await b.get("/api/v1/connection-requests")).json()[0]
    assert outgoing["direction"] == "outgoing" and incoming["direction"] == "incoming"
    assert outgoing["peer"]["profile"]["interests"] == OTHER["interests"]
    assert incoming["peer"]["profile"]["interests"] == PROFILE["interests"]
    for row in (outgoing, incoming):
        card = row["peer"]
        assert card["alias"] == alias and card["avatarSeed"] == seed
        assert card["matchLabel"] in ("many", "some")
        assert 0 < len(card["reasons"]) <= 3
        assert not ({"userId", "id", "score", "sources", "identity"} & card.keys())
    c, _ = await add_actor(app, 2)
    await publish(c)
    assert (await c.get("/api/v1/connection-requests")).json() == []
    assert (
        await c.post(
            f"/api/v1/connection-requests/{incoming['id']}/decline",
            json={"expectedVersion": incoming["version"]},
            headers=key(),
        )
    ).status_code == 404


async def test_peer_card_disappears_once_the_pair_is_ineligible(clients):
    _, actors, refs = await published_pair(clients)
    (a, _), (b, _) = actors
    await a.post("/api/v1/connection-requests", json={"candidateRef": refs[0]}, headers=key())
    assert (await b.get("/api/v1/connection-requests")).json()[0]["peer"] is not None
    blocked = await b.post("/api/v1/blocks", json={"peerRef": refs[1]}, headers=key())
    assert blocked.status_code == 201, blocked.text
    for client in (a, b):
        row = (await client.get("/api/v1/connection-requests")).json()[0]
        assert row["status"] == "invalidated" and row["peer"] is None
