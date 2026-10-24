import time
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.runtime import Proposal
from app.infrastructure.database.models import Memory, User

pytestmark = pytest.mark.postgres


def key():
    return {"Idempotency-Key": str(uuid4())}


async def test_proposal_confirmation_requires_memory_consent_exact_payload_and_current_version(
    clients,
):
    app, actors = clients
    a, uid = actors[0]
    await a.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        from app.infrastructure.database.models import AuthSession

        own = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        proposal = Proposal(
            uid,
            own.id,
            "may",
            "Mình thích đọc sách",
            "memory",
            user.data_version,
            time.monotonic() + 900,
        )
    app.state.ai.proposals[proposal.id] = proposal
    endpoint = f"/api/v1/proposals/{proposal.id}/confirm"
    denied = await a.post(
        endpoint, json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"}, headers=key()
    )
    assert denied.status_code == 403
    assert (await a.get("/api/v1/memories")).json() == []
    await a.put(
        "/api/v1/consents/MEM",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    # Changing consent invalidates old previews; a fresh source must be deliberately approved.
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        proposal = Proposal(
            uid,
            own.id,
            "may",
            "Mình thích đọc sách",
            "memory",
            user.data_version,
            time.monotonic() + 900,
        )
    app.state.ai.proposals[proposal.id] = proposal
    endpoint = f"/api/v1/proposals/{proposal.id}/confirm"
    approval_key = key()
    approved = await a.post(
        endpoint,
        json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"},
        headers=approval_key,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "succeeded"
    replay = await a.post(
        endpoint,
        json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"},
        headers=approval_key,
    )
    assert replay.status_code == 200 and replay.json() == approved.json()
    values = (await a.get("/api/v1/memories")).json()
    assert len(values) == 1 and values[0]["text"] == "Mình đọc vào buổi sáng"
    assert (await actors[1][0].get("/api/v1/memories")).json() == []


async def test_memory_remains_manageable_with_ai_off_but_deleted_text_is_not_returned(clients):
    app, actors = clients
    a, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        memory = Memory(
            user_id=uid, bot_id="may", text="An approved preference", proposal_id=uuid4()
        )
        db.add(memory)
        await db.flush()
        identity = memory.id
    records = (await a.get("/api/v1/memories")).json()
    assert records[0]["id"] == str(identity)
    edited = await a.patch(
        f"/api/v1/memories/{identity}",
        json={"text": "Edited by user", "expectedVersion": 1},
        headers=key(),
    )
    assert edited.status_code == 200 and edited.json()["version"] == 2
    headers = key()
    removed = await a.request(
        "DELETE", f"/api/v1/memories/{identity}", json={"expectedVersion": 2}, headers=headers
    )
    assert removed.status_code == 200
    replay = await a.request(
        "DELETE", f"/api/v1/memories/{identity}", json={"expectedVersion": 2}, headers=headers
    )
    assert replay.json() == removed.json()
    assert (await a.get("/api/v1/memories")).json() == []


async def test_reject_proposal_discards_it_without_saving_a_private_item_or_memory(clients):
    app, actors = clients
    a, uid = actors[0]
    from app.infrastructure.database.models import AuthSession

    async with app.state.database.sessions() as db:
        own = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
    proposal = Proposal(
        uid, own.id, "guong", "Một giả thuyết", "private_item", 1, time.monotonic() + 900
    )
    app.state.ai.proposals[proposal.id] = proposal
    result = await a.post(
        f"/api/v1/proposals/{proposal.id}/reject", json={"expectedVersion": 1}, headers=key()
    )
    assert result.status_code == 200, result.text
    assert proposal.id not in app.state.ai.proposals
    assert (await a.get("/api/v1/profiles/private-items")).json() == []
    assert (await a.get("/api/v1/memories")).json() == []
