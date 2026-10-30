"""Owner journal behavior: multiple moments, drafts, receipts and private lifecycle."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Mood
from tests.social_helpers import key

pytestmark = pytest.mark.postgres


def today():
    return datetime.now(ZoneInfo("Asia/Bangkok")).date()


def entry(text="Một khoảnh khắc", **changes):
    return {
        "localDate": str(today()),
        "mood": 4,
        "text": text,
        "emotions": ["bình yên"],
        "factors": ["gia đình"],
        "status": "saved",
        **changes,
    }


async def create(client, **changes):
    response = await client.post("/api/v1/journal/entries", json=entry(**changes), headers=key())
    assert response.status_code == 201, response.text
    return response.json()


async def test_multiple_same_day_entries_preserve_legacy_mood_and_create_replays(clients):
    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        legacy = Mood(
            user_id=uid, local_date=today(), value=2, note="legacy", timezone="Asia/Bangkok"
        )
        db.add(legacy)
    headers = key()
    first = await client.post("/api/v1/journal/entries", json=entry(), headers=headers)
    assert first.status_code == 201, first.text
    replay = await client.post("/api/v1/journal/entries", json=entry(), headers=headers)
    assert replay.json() == first.json()
    conflict = await client.post("/api/v1/journal/entries", json=entry("khác"), headers=headers)
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    second = await create(client, text="Buổi chiều")
    assert second["id"] != first.json()["id"]
    listed = (await client.get("/api/v1/journal/entries")).json()
    assert listed["total"] == 2
    assert [item["id"] for item in listed["items"]] == [second["id"], first.json()["id"]]
    mood = (await client.get("/api/v1/moods")).json()
    assert [(row["note"], row["value"], row["version"]) for row in mood] == [("legacy", 2, 1)]


async def test_owner_reads_edits_and_deletes_use_versions_and_receipts(clients):
    _, actors = clients
    (owner, _), (other, _) = actors
    row = await create(owner)
    path = f"/api/v1/journal/entries/{row['id']}"
    assert (await other.get(path)).status_code == 404
    assert (await other.put(path, json=entry(expectedVersion=1), headers=key())).status_code == 404
    denied = await other.request("DELETE", path, json={"expectedVersion": 1}, headers=key())
    assert denied.status_code == 404
    headers = key()
    changed = await owner.put(path, json=entry("Đã sửa", expectedVersion=1), headers=headers)
    assert changed.status_code == 200, changed.text
    assert (changed.json()["text"], changed.json()["version"]) == ("Đã sửa", 2)
    assert (
        await owner.put(path, json=entry("Đã sửa", expectedVersion=1), headers=headers)
    ).json() == changed.json()
    stale = await owner.put(path, json=entry("cũ", expectedVersion=1), headers=key())
    assert stale.json()["error"]["code"] == "STALE_VERSION"
    delete_headers = key()
    gone = await owner.request("DELETE", path, json={"expectedVersion": 2}, headers=delete_headers)
    assert gone.status_code == 200, gone.text
    assert (
        await owner.request("DELETE", path, json={"expectedVersion": 2}, headers=delete_headers)
    ).json() == gone.json()
    assert (await owner.get(path)).status_code == 404


async def test_draft_search_mood_media_and_pagination_filters(clients):
    from app.modules.journal.models import JournalMedia

    app, actors = clients
    client, uid = actors[0]
    a = await create(client, text="100% bình yên", mood=5)
    b = await create(client, text="100 điều vui", mood=3)
    draft = await create(client, text="bản nháp", status="draft")
    async with app.state.database.sessions.begin() as db:
        db.add(
            JournalMedia(
                user_id=uid,
                entry_id=UUID(a["id"]),
                type="image",
                object_path=str(uuid4()),
                mime_type="image/png",
                size_bytes=10,
                status="ready",
            )
        )
    listed = (await client.get("/api/v1/journal/entries", params={"limit": 1})).json()
    assert (listed["total"], listed["offset"], listed["limit"]) == (2, 0, 1)
    assert listed["items"][0]["id"] == b["id"]
    second = (await client.get("/api/v1/journal/entries", params={"offset": 1, "limit": 1})).json()
    assert second["items"][0]["id"] == a["id"]
    for params in ({"q": "100%"}, {"mood": 5}, {"media": "image"}, {"media": "any"}):
        result = (await client.get("/api/v1/journal/entries", params=params)).json()
        assert [row["id"] for row in result["items"]] == [a["id"]]
        assert "objectPath" not in str(result)
    result = (await client.get("/api/v1/journal/entries", params={"status": "draft"})).json()
    assert [row["id"] for row in result["items"]] == [draft["id"]]
    assert (await actors[1][0].get("/api/v1/journal/entries", params={"q": "bình"})).json()[
        "total"
    ] == 0


async def test_entry_boundaries_and_account_timezone(clients):
    from sqlalchemy import update

    from app.infrastructure.database.models import User

    app, actors = clients
    client, uid = actors[0]
    for changes in (
        {"mood": True},
        {"mood": 0},
        {"text": "x" * 10001},
        {"emotions": ["x"] * 13},
        {"factors": [42]},
        {"userId": str(uid)},
        {"localDate": str(today() + timedelta(days=1))},
        {"localDate": str(today() - timedelta(days=90))},
    ):
        response = await client.post(
            "/api/v1/journal/entries", json=entry(**changes), headers=key()
        )
        assert response.status_code == 422, (changes, response.text)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(timezone="Etc/GMT+12"))
    local = datetime.now(ZoneInfo("Etc/GMT+12")).date()
    created = await create(client, localDate=str(local), text="x" * 10000)
    assert created["timezone"] == "Etc/GMT+12"
    assert (
        await client.get("/api/v1/journal/entries", params={"from": str(local + timedelta(days=1))})
    ).status_code == 422
    assert (await client.get("/api/v1/journal/entries", params={"limit": 51})).status_code == 422


async def test_edit_preserves_creation_timezone_after_account_timezone_changes(clients):
    from sqlalchemy import update

    from app.infrastructure.database.models import User
    from app.modules.journal.models import JournalEntry

    app, actors = clients
    client, uid = actors[0]
    day = str(today() - timedelta(days=1))
    created = await create(client, localDate=day)
    assert created["timezone"] == "Asia/Bangkok"
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(timezone="Etc/GMT+12"))
    path = f"/api/v1/journal/entries/{created['id']}"
    edited = await client.put(
        path, json=entry("Đã sửa", localDate=day, expectedVersion=1), headers=key()
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["timezone"] == "Asia/Bangkok"
    assert edited.json()["createdAt"] == created["createdAt"]
    assert (await client.get(path)).json()["timezone"] == "Asia/Bangkok"
    async with app.state.database.sessions() as db:
        assert (await db.get(JournalEntry, UUID(created["id"]))).timezone == "Asia/Bangkok"


async def test_query_range_checks_current_account_local_active_dates(clients):
    from sqlalchemy import update

    from app.infrastructure.database.models import User

    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(timezone="Etc/GMT+12"))
    local_today = datetime.now(ZoneInfo("Etc/GMT+12")).date()
    oldest = local_today - timedelta(days=89)
    created = await create(client, localDate=str(oldest))
    valid = await client.get(
        "/api/v1/journal/entries", params={"from": str(oldest), "to": str(local_today)}
    )
    assert valid.status_code == 200, valid.text
    assert [row["id"] for row in valid.json()["items"]] == [created["id"]]
    for bounds in (
        {"from": str(oldest - timedelta(days=1))},
        {"to": str(local_today + timedelta(days=1))},
        {"from": str(local_today), "to": str(local_today - timedelta(days=1))},
    ):
        invalid = await client.get("/api/v1/journal/entries", params=bounds)
        assert invalid.status_code == 422, (bounds, invalid.text)
        assert invalid.json()["error"]["code"] == "INVALID_RANGE"


async def test_entry_delete_queues_media_and_invalidates_exports(clients):
    from app.modules.journal.models import JournalMedia, JournalStorageDeletion

    app, actors = clients
    client, uid = actors[0]
    row = await create(client)
    async with app.state.database.sessions.begin() as db:
        db.add(
            JournalMedia(
                user_id=uid,
                entry_id=UUID(row["id"]),
                type="audio",
                object_path="private/delete-me",
                mime_type="audio/webm",
                size_bytes=10,
                status="ready",
            )
        )
    exported = await client.post("/api/v1/exports", json={"scopes": ["journal"]}, headers=key())
    assert exported.status_code == 201, exported.text
    path = f"/api/v1/journal/entries/{row['id']}"
    response = await client.request("DELETE", path, json={"expectedVersion": 1}, headers=key())
    assert response.status_code == 200
    assert (
        await client.get(f"/api/v1/exports/{exported.json()['id']}/download")
    ).status_code == 410
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(JournalMedia))).all() == []
        assert (await db.scalars(select(JournalStorageDeletion.object_path))).all() == [
            "private/delete-me"
        ]


async def test_journal_export_and_scope_deletion_leave_moods_alone(clients):
    app, actors = clients
    client, uid = actors[0]
    row = await create(client, text="riêng tư")
    async with app.state.database.sessions.begin() as db:
        db.add(Mood(user_id=uid, local_date=today(), value=3, timezone="Asia/Bangkok"))
    exported = await client.post("/api/v1/exports", json={"scopes": ["journal"]}, headers=key())
    assert exported.status_code == 201, exported.text
    downloaded = await client.get(f"/api/v1/exports/{exported.json()['id']}/download")
    assert downloaded.json()["journal"][0]["text"] == "riêng tư"
    version = (await client.get("/api/v1/session")).json()["dataVersion"]
    deleting = await client.post(
        "/api/v1/data-deletions",
        json={"scope": "journal", "expectedVersion": version},
        headers=key(),
    )
    assert deleting.status_code == 202, deleting.text
    from app.modules.users.lifecycle import process_deletions

    await process_deletions(app)
    assert (await client.get(f"/api/v1/journal/entries/{row['id']}")).status_code == 404
    assert len((await client.get("/api/v1/moods")).json()) == 1


async def test_journal_retention_hides_and_purges_old_entries_with_durable_cleanup(clients):
    from app.jobs.retention import purge_expired
    from app.modules.journal.models import JournalEntry, JournalMedia, JournalStorageDeletion

    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        old = JournalEntry(
            user_id=uid,
            local_date=today() - timedelta(days=90),
            timezone="Asia/Bangkok",
            mood=3,
            text="old",
        )
        kept = JournalEntry(
            user_id=uid,
            local_date=today() - timedelta(days=89),
            timezone="Asia/Bangkok",
            mood=4,
            text="kept",
        )
        db.add_all([old, kept])
        await db.flush()
        db.add(
            JournalMedia(
                user_id=uid,
                entry_id=old.id,
                type="video",
                object_path="expired/video",
                mime_type="video/mp4",
                size_bytes=10,
            )
        )
        old_id = old.id
    assert (await client.get(f"/api/v1/journal/entries/{old_id}")).status_code == 404
    assert (await client.get("/api/v1/journal/entries")).json()["total"] == 1
    await purge_expired(app)
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(JournalEntry.text))).all() == ["kept"]
        assert (await db.scalars(select(JournalStorageDeletion.object_path))).all() == [
            "expired/video"
        ]


@pytest.mark.parametrize("scope", ["all_private", "account"])
async def test_whole_private_erasure_keeps_durable_media_cleanup(clients, scope):
    from app.modules.journal.models import JournalEntry, JournalMedia, JournalStorageDeletion
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    client, uid = actors[0]
    row = await create(client)
    async with app.state.database.sessions.begin() as db:
        db.add(
            JournalMedia(
                user_id=uid,
                entry_id=UUID(row["id"]),
                type="image",
                object_path="erased/object",
                mime_type="image/png",
                size_bytes=10,
                status="pending",
            )
        )
    version = (await client.get("/api/v1/session")).json()["dataVersion"]
    response = await client.post(
        "/api/v1/data-deletions", json={"scope": scope, "expectedVersion": version}, headers=key()
    )
    assert response.status_code == 202, response.text
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (
            await db.scalars(select(JournalEntry).where(JournalEntry.user_id == uid))
        ).all() == []
        assert (await db.scalars(select(JournalMedia))).all() == []
        assert (await db.scalars(select(JournalStorageDeletion.object_path))).all() == [
            "erased/object"
        ]


async def test_export_all_six_scopes_fits_existing_job_scope(clients):
    _, actors = clients
    client, _ = actors[0]
    response = await client.post(
        "/api/v1/exports",
        json={
            "scopes": [
                "account",
                "memories",
                "moods",
                "journal",
                "consents",
                "social",
            ]
        },
        headers=key(),
    )
    assert response.status_code == 201, response.text
    assert (
        response.json()["scope"] == "account,memories,moods,journal,consents,social"
    )
