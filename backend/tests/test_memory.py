import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select, text

from app.ai.memory import create_proposal
from app.ai.memory_models import MemoryProposal
from app.core.errors import DomainError
from app.core.security import Actor, digest
from app.infrastructure.database.models import AuthSession, Memory, User, now

pytestmark = pytest.mark.postgres


def key():
    return {"Idempotency-Key": str(uuid4())}


async def enable(client, purpose):
    response = await client.put(
        f"/api/v1/consents/{purpose}",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert response.status_code == 200, response.text


async def seed_proposal(app, uid, **values):
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        return await create_proposal(
            db,
            Actor(uid, session.id, user.auth_version),
            values.pop("bot_id", "may"),
            values.pop("text", "Mình thích đọc sách"),
            user.data_version,
            **values,
        )


async def test_durable_proposal_is_owner_scoped_and_survives_runtime_replacement(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    await enable(client, "MEM")
    proposal = await seed_proposal(app, uid)
    from app.ai.runtime import AiRuntime

    await app.state.ai.close()
    app.state.ai = AiRuntime(app.state.settings, app.state.database)
    items = (await client.get("/api/v1/proposals")).json()
    assert items[0]["id"] == str(proposal.id)
    assert items[0]["status"] == "pending" and items[0]["expiresAt"]
    assert (await actors[1][0].get("/api/v1/proposals")).json() == []
    foreign = await actors[1][0].post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert foreign.status_code == 404
    approved = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert approved.status_code == 200, approved.text


async def test_another_valid_login_of_same_owner_can_confirm_pending_proposal(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    proposal = await seed_proposal(app, uid)
    token, csrf, sid = str(uuid4()), str(uuid4()), uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(
            AuthSession(
                user_id=uid,
                token_hash=digest(token),
                csrf_hash=digest(csrf),
                provider_session_id=sid,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.execute(
            text("insert into auth.sessions(id,user_id) values (:id,:uid)"), {"id": sid, "uid": uid}
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"moodprint_session": token},
        headers={"X-CSRF-Token": csrf},
    ) as other_session:
        response = await other_session.post(
            f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
        )
    assert response.status_code == 200, response.text
    async with app.state.database.sessions() as db:
        stored = await db.get(MemoryProposal, proposal.id)
        assert stored.status == "approved" and stored.text == ""


async def test_old_terminal_proposals_are_purged_without_removing_pending_previews(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    old = await seed_proposal(app, uid)
    current = await seed_proposal(app, uid)
    response = await client.post(
        f"/api/v1/proposals/{old.id}/reject", json={"expectedVersion": 1}, headers=key()
    )
    assert response.status_code == 200
    async with app.state.database.sessions.begin() as db:
        stored = await db.get(MemoryProposal, old.id)
        stored.decided_at = now() - timedelta(days=31)
    import app.ai.memory as lifecycle

    async with app.state.database.sessions.begin() as db:
        assert await lifecycle.purge_proposals(db) == 1
    async with app.state.database.sessions() as db:
        assert await db.get(MemoryProposal, old.id) is None
        assert (await db.get(MemoryProposal, current.id)).status == "pending"


async def test_simultaneous_confirmations_create_exactly_one_memory(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    await enable(client, "MEM")
    proposal = await seed_proposal(app, uid)
    endpoint = f"/api/v1/proposals/{proposal.id}/confirm"
    replies = await asyncio.gather(
        *[client.post(endpoint, json={"expectedVersion": 1}, headers=key()) for _ in range(5)]
    )
    assert [reply.status_code for reply in replies] == [200] * 5
    assert all(reply.json() == replies[0].json() for reply in replies)
    assert len((await client.get("/api/v1/memories")).json()) == 1
    conflict = await client.post(
        endpoint, json={"expectedVersion": 1, "editedText": "Different approval"}, headers=key()
    )
    assert conflict.status_code == 409
    rejected = await client.post(
        f"/api/v1/proposals/{proposal.id}/reject", json={"expectedVersion": 1}, headers=key()
    )
    assert rejected.status_code == 409


async def test_expired_proposal_persists_expired_state_and_erases_preview(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    proposal = await seed_proposal(app, uid)
    async with app.state.database.sessions.begin() as db:
        stored = await db.get(MemoryProposal, proposal.id)
        stored.expires_at = now() - timedelta(seconds=1)
    response = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert response.status_code == 410
    async with app.state.database.sessions() as db:
        stored = await db.get(MemoryProposal, proposal.id)
        assert stored.status == "expired" and stored.text == ""
    assert (await client.get("/api/v1/memories")).json() == []


async def test_caunoi_cannot_propose_memory_and_consent_is_rechecked(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    await enable(client, "MEM")
    with pytest.raises(DomainError) as forbidden:
        await seed_proposal(app, uid, bot_id="caunoi")
    assert forbidden.value.code == "MEMORY_BOT_FORBIDDEN"
    proposal = await seed_proposal(app, uid)
    ignored = await client.put(
        "/api/v1/consents/MEM",
        json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert ignored.status_code == 200, ignored.text
    assert ignored.json()["consents"]["MEM"]["enabled"] is True
    response = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/v1/memories")).json() != []


async def test_approval_grants_memory_use_for_only_approved_content(
    clients,
):
    app, actors = clients
    a, uid = actors[0]
    await a.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    proposal = await seed_proposal(app, uid)
    endpoint = f"/api/v1/proposals/{proposal.id}/confirm"
    assert (await a.get("/api/v1/memories")).json() == []
    approval_key = key()
    approved = await a.post(
        endpoint,
        json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"},
        headers=approval_key,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "succeeded"
    assert (await a.get("/api/v1/session")).json()["consents"]["MEM"]["enabled"]
    replay = await a.post(
        endpoint,
        json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"},
        headers=approval_key,
    )
    assert replay.status_code == 200 and replay.json() == approved.json()
    independent_retry = await a.post(
        endpoint,
        json={"expectedVersion": 1, "editedText": "Mình đọc vào buổi sáng"},
        headers=key(),
    )
    assert independent_retry.status_code == 200, independent_retry.text
    assert independent_retry.json() == approved.json()
    values = (await a.get("/api/v1/memories")).json()
    assert len(values) == 1 and values[0]["text"] == "Mình đọc vào buổi sáng"
    assert (await actors[1][0].get("/api/v1/memories")).json() == []


async def test_rejected_proposal_does_not_grant_memory_permission(clients):
    app, actors = clients
    a, uid = actors[0]
    await enable(a, "AI")
    proposal = await seed_proposal(app, uid)
    response = await a.post(
        f"/api/v1/proposals/{proposal.id}/reject",
        json={"expectedVersion": 1}, headers=key(),
    )
    assert response.status_code == 200, response.text
    assert (await a.get("/api/v1/session")).json()["consents"]["MEM"]["enabled"] is True
    assert (await a.get("/api/v1/memories")).json() == []


async def test_first_approval_keeps_other_pending_proposals_reviewable(clients):
    app, actors = clients
    a, uid = actors[0]
    await enable(a, "AI")
    first = await seed_proposal(app, uid, text="Tôi thích đọc sách")
    second = await seed_proposal(app, uid, text="Tôi thích đi bộ")
    for proposal in (first, second):
        response = await a.post(
            f"/api/v1/proposals/{proposal.id}/confirm",
            json={"expectedVersion": 1}, headers=key(),
        )
        assert response.status_code == 200, response.text
    assert len((await a.get("/api/v1/memories")).json()) == 2


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


async def test_reject_proposal_discards_it_without_saving_a_memory(clients):
    app, actors = clients
    a, uid = actors[0]
    await enable(a, "AI")
    proposal = await seed_proposal(app, uid)
    result = await a.post(
        f"/api/v1/proposals/{proposal.id}/reject", json={"expectedVersion": 1}, headers=key()
    )
    assert result.status_code == 200, result.text
    async with app.state.database.sessions() as db:
        stored = await db.get(MemoryProposal, proposal.id)
        assert stored.status == "rejected" and stored.text == ""
    replay = await a.post(
        f"/api/v1/proposals/{proposal.id}/reject", json={"expectedVersion": 1}, headers=key()
    )
    assert replay.json() == result.json()
    assert (await a.get("/api/v1/memories")).json() == []


async def test_approving_one_proposal_does_not_stale_sibling_proposals_from_the_same_turn(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    await enable(client, "MEM")
    first = await seed_proposal(app, uid, text="Mình thích đọc sách")
    second = await seed_proposal(app, uid, text="Mình hay đi bộ buổi tối")
    async with app.state.database.sessions.begin() as db:
        # Unrelated private data revisions (for example a mood entry) must not
        # invalidate an approval whose consent context is unchanged.
        (await db.get(User, uid)).data_version += 1
    for proposal in (first, second):
        response = await client.post(
            f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
        )
        assert response.status_code == 200, response.text
    texts = sorted(m["text"] for m in (await client.get("/api/v1/memories")).json())
    assert texts == ["Mình hay đi bộ buổi tối", "Mình thích đọc sách"]


async def test_consent_withdrawal_and_regrant_still_stales_pending_proposal(clients):
    app, actors = clients
    client, uid = actors[0]
    await enable(client, "AI")
    await enable(client, "MEM")
    proposal = await seed_proposal(app, uid)
    for enabled in (False, True):
        changed = await client.put(
            "/api/v1/consents/MEM",
            json={"enabled": enabled, "expectedVersion": 1, "policyVersion": "v1"},
            headers=key(),
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["consents"]["MEM"]["enabled"] is True
        assert changed.json()["consents"]["MEM"]["version"] == 1
    response = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/v1/memories")).json() != []
