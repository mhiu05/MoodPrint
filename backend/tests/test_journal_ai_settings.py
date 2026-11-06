"""Owner switches must version, replay, revoke derivatives, and exclude guests."""


from pydantic import SecretStr
from sqlalchemy import delete, func, select

from app.infrastructure.database.models import AiRun, User
from app.modules.journal.ai_models import JournalAiJob, JournalAiSettings, JournalEntryEmbedding
from tests.guest_helpers import add_guest
from tests.social_helpers import key
from tests.test_journal import create
from tests.test_journal_intelligence_migration import seed_derivatives


def body(**changes):
    return {"embeddingEnabled": True, "autoMemoryEnabled": True,
            "noticeVersion": "journal-ai-v1", "expectedVersion": 1, **changes}


async def test_absent_row_means_enabled_and_is_reported_available(journal_configured):
    _app, actors = journal_configured
    response = await actors[0][0].get("/api/v1/journal/ai-settings")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "embeddingEnabled": True, "autoMemoryEnabled": True, "embeddingAvailable": True,
        "autoMemoryAvailable": False, "noticeVersion": "journal-ai-v1", "version": 1,
        "indexedEntries": 0, "pendingEntries": 0, "autoMemories": 0,
    }


async def test_put_is_idempotent_and_versioned(journal_configured):
    app, actors = journal_configured
    client, uid = actors[0]
    headers = key()
    first = await client.put("/api/v1/journal/ai-settings", json=body(embeddingEnabled=False), headers=headers)
    assert first.status_code == 200, first.text
    replay = await client.put("/api/v1/journal/ai-settings", json=body(embeddingEnabled=False), headers=headers)
    assert replay.json() == first.json()
    assert first.json()["version"] == 2
    stale = await client.put("/api/v1/journal/ai-settings", json=body(), headers=key())
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_VERSION"
    async with app.state.database.sessions() as db:
        assert (await db.get(JournalAiSettings, uid)).version == 2


async def test_turning_embedding_off_deletes_vectors_cancels_jobs_and_running_turns(journal_configured):
    from uuid import UUID

    app, actors = journal_configured
    client, uid = actors[0]
    entry = await create(client)
    async with app.state.database.sessions.begin() as db:
        # Route enqueue is exercised separately; this fixture seeds its own job.
        await db.execute(delete(JournalAiJob).where(JournalAiJob.entry_id == UUID(entry["id"])))
        await seed_derivatives(db, uid, UUID(entry["id"]))
        db.add(AiRun(user_id=uid, bot_id="nhatky", origin="journal", status="running"))
        before = (await db.get(User, uid)).data_version
    response = await client.put("/api/v1/journal/ai-settings", json=body(embeddingEnabled=False), headers=key())
    assert response.status_code == 200, response.text
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(JournalEntryEmbedding)) == 0
        assert (await db.scalar(select(JournalAiJob))).status == "cancelled"
        assert (await db.scalar(select(AiRun))).status == "cancelled"
        assert (await db.get(User, uid)).data_version == before + 1


async def test_counts_are_owner_scoped(journal_configured):
    from uuid import UUID

    app, actors = journal_configured
    entry = await create(actors[0][0])
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(JournalAiJob).where(JournalAiJob.entry_id == UUID(entry["id"])))
        await seed_derivatives(db, actors[0][1], UUID(entry["id"]))
    first = (await actors[0][0].get("/api/v1/journal/ai-settings")).json()
    other = (await actors[1][0].get("/api/v1/journal/ai-settings")).json()
    assert (first["indexedEntries"], first["pendingEntries"], first["autoMemories"]) == (1, 1, 1)
    assert (other["indexedEntries"], other["pendingEntries"], other["autoMemories"]) == (0, 0, 0)


async def test_guest_is_refused(journal_configured):
    app, _actors = journal_configured
    guest = await add_guest(app)
    for method, kwargs in (("get", {}), ("put", {"json": body(), "headers": key()})):
        response = await getattr(guest.client, method)("/api/v1/journal/ai-settings", **kwargs)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "REGISTERED_REQUIRED"


async def test_stored_disable_does_not_turn_semantic_search_off(journal_configured):
    from app.modules.journal.ai_settings import journal_ai_allowed

    app, actors = journal_configured
    client, uid = actors[0]
    response = await client.put(
        "/api/v1/journal/ai-settings",
        json=body(embeddingEnabled=False, autoMemoryEnabled=False),
        headers=key(),
    )
    assert response.status_code == 200, response.text
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        assert await journal_ai_allowed(db, user, app.state.settings, "embed") == 2


async def test_unavailable_embedding_still_saves_user_preference(journal_configured):
    app, actors = journal_configured
    app.state.settings.voyage_api_key = SecretStr("")
    response = await actors[0][0].put("/api/v1/journal/ai-settings", json=body(), headers=key())
    assert response.status_code == 200
    assert response.json()["embeddingEnabled"] is True
    assert response.json()["embeddingAvailable"] is False
