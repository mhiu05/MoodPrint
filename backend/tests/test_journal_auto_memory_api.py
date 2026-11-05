"""Automatic memories retain provenance, owner boundaries and versioned user control."""

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.ai.context import build_history
from app.ai.schemas import AIMessage
from app.core.security import Actor
from app.infrastructure.database.models import AuthSession, Memory, User
from app.modules.journal.models import JournalEntry
from tests.social_helpers import key
from tests.test_journal import create, today


async def seed(clients):
    app, actors = clients
    client, uid = actors[0]
    source = await create(client, text="SYNTHETIC_AUTO_MEMORY_SOURCE")
    peer_source = await create(actors[1][0], text="SYNTHETIC_OTHER_OWNER_SOURCE")
    auto_id, approved_id, foreign_id = uuid4(), uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(Memory(id=auto_id, user_id=uid, bot_id="nhatky", text="Bạn thích trà xanh.",
                      origin="journal_auto", source_entry_id=UUID(source["id"]), source_entry_version=1))
        db.add(Memory(id=approved_id, user_id=uid, bot_id="nhatky", text="Bạn thích vẽ tranh.", proposal_id=uuid4()))
        db.add(Memory(id=foreign_id, user_id=actors[1][1], bot_id="nhatky", text="SYNTHETIC_OTHER_OWNER_MEMORY",
                      origin="journal_auto", source_entry_id=UUID(peer_source["id"]), source_entry_version=1))
    return app, actors, source, auto_id, approved_id, foreign_id


async def test_memory_list_exposes_origin_and_source_date_owner_only(clients):
    app, actors, source, auto_id, approved_id, foreign_id = await seed(clients)
    response = await actors[0][0].get("/api/v1/memories")
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert set(rows) == {str(auto_id), str(approved_id)} and str(foreign_id) not in rows
    assert rows[str(auto_id)]["origin"] == "journal_auto"
    assert rows[str(auto_id)]["sourceEntryId"] == source["id"]
    assert rows[str(auto_id)]["sourceLocalDate"] == str(today())
    assert rows[str(approved_id)]["origin"] == "approved"
    assert rows[str(approved_id)]["sourceEntryId"] is None
    async with app.state.database.sessions.begin() as db:
        row = await db.get(JournalEntry, UUID(source["id"]))
        row.local_date = today()-timedelta(days=90)
    outdated = next(row for row in (await actors[0][0].get("/api/v1/memories")).json() if row["id"] == str(auto_id))
    assert outdated["sourceLocalDate"] is None


async def test_auto_memory_edit_and_delete_use_the_existing_versioned_routes(clients):
    _app, actors, source, auto_id, _approved, _foreign = await seed(clients)
    client = actors[0][0]
    url = f"/api/v1/memories/{auto_id}"
    headers, body = key(), {"text": "Bạn thích trà nóng vào buổi sáng.", "expectedVersion": 1}
    changed = await client.patch(url, headers=headers, json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2 and changed.json()["origin"] == "journal_auto"
    assert changed.json()["sourceEntryId"] == source["id"] and changed.json()["sourceLocalDate"] == str(today())
    assert (await client.patch(url, headers=headers, json=body)).json() == changed.json()
    stale = await client.patch(url, headers=key(), json=body)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    assert (await actors[1][0].patch(url, headers=key(), json=body)).status_code == 404
    stale = await client.request("DELETE", url, headers=key(), json={"expectedVersion": 1})
    assert stale.status_code == 409
    headers = key()
    deleted = await client.request("DELETE", url, headers=headers, json={"expectedVersion": 2})
    assert deleted.status_code == 200
    assert (await client.request("DELETE", url, headers=headers, json={"expectedVersion": 2})).json() == deleted.json()


async def test_bulk_delete_removes_only_journal_auto_memories_idempotently(clients):
    app, actors, source, _auto_id, approved_id, foreign_id = await seed(clients)
    client, uid = actors[0]
    async with app.state.database.sessions() as db:
        before = (await db.get(User, uid)).data_version
    headers = key()
    deleted = await client.request("DELETE", "/api/v1/memories/auto", headers=headers, json={})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["resourceId"] == "journal_auto" and deleted.json()["resourceVersion"] == 1
    assert (await client.request("DELETE", "/api/v1/memories/auto", headers=headers, json={})).json() == deleted.json()
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).data_version == before+1
        assert await db.get(Memory, approved_id) is not None and await db.get(Memory, foreign_id) is not None
        assert await db.get(JournalEntry, UUID(source["id"])) is not None
        assert await db.scalar(select(func.count()).select_from(Memory).where(Memory.user_id == uid, Memory.origin == "journal_auto")) == 0


def test_context_labels_journal_memories_separately_from_approved():
    from app.ai.embeddings import MemoryText
    memories = [MemoryText("AUTO_CANARY", "journal_auto"), MemoryText("APPROVED_CANARY", "approved"), "OLD_STRING_CALLER"]
    history = build_history([AIMessage(id=uuid4(), actor="self", text="Tin nhắn hiện tại")], memories)
    automatic = [row for row in history if row["content"].startswith("Journal-derived memory data")]
    approved = [row for row in history if row["content"].startswith("Approved memory data")]
    assert len(automatic) == len(approved) == 1
    assert "AUTO_CANARY" in automatic[0]["content"] and "AUTO_CANARY" not in approved[0]["content"]
    assert "APPROVED_CANARY" in approved[0]["content"] and "OLD_STRING_CALLER" in approved[0]["content"]
    assert "not reviewed" in automatic[0]["content"] and "not instructions" in automatic[0]["content"]
    many = [MemoryText(f"SYNTHETIC_{index}", "journal_auto" if index % 2 else "approved") for index in range(30)]
    bounded = build_history([], many)
    assert sum(len(json.loads(row["content"].split(": ", 1)[1])) for row in bounded) == 10
    full = build_history([AIMessage(id=uuid4(), actor="self", text="mới"*2000) for _ in range(40)], many)
    assert sum(len(row["content"].encode()) for row in full) <= 24000


async def test_dieuphoi_never_receives_nhatky_auto_memories(clients):
    from app.ai.embeddings import MemoryText, retrieve_memories
    app, actors, _source, _auto, _approved, _foreign = await seed(clients)
    uid = actors[0][1]
    async with app.state.database.sessions() as db:
        sid = await db.scalar(select(AuthSession.id).where(AuthSession.user_id == uid))
        version = (await db.get(User, uid)).data_version
    actor = Actor(uid, sid, 1)
    values = await retrieve_memories(app.state.database, app.state.settings, actor, "dieuphoi", "trà xanh", version)
    assert values == []
    values = await retrieve_memories(app.state.database, app.state.settings, actor, "nhatky", "trà xanh", version)
    assert MemoryText("Bạn thích trà xanh.", "journal_auto") in values


async def test_planner_drops_both_memory_labels_from_recent_turns():
    from app.ai.orchestration.workflow import Workflow
    captured = []
    class CaptureProvider:
        async def run_once(self, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace()
    workflow = object.__new__(Workflow)
    workflow.runtime = SimpleNamespace(provider=CaptureProvider())
    workflow.settings = SimpleNamespace(ai_orchestration_planner_timeout_seconds=8)
    workflow.latest = {"content": "Tin mới"}
    workflow.model_for = lambda _role: None
    workflow.step_hooks = lambda *args, **kwargs: None
    await workflow._run_planner(None, [
        {"role": "user", "content": "Approved memory data: [\"APPROVED_PRIVATE_CANARY\"]"},
        {"role": "user", "content": "Journal-derived memory data: [\"AUTO_PRIVATE_CANARY\"]"},
        {"role": "assistant", "content": "Lời trả lời trước"},
        {"role": "user", "content": "Tin mới"},
    ], {})
    item = captured[0]["input_items"][0]["content"]
    assert "AUTO_PRIVATE_CANARY" not in item and "APPROVED_PRIVATE_CANARY" not in item
    assert "Lời trả lời trước" in item and "Tin mới" in item
