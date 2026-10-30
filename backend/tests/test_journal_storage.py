"""Private journal capabilities, verification, recovery and durable object deletion."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from app.infrastructure.database.models import now
from tests.social_helpers import key
from tests.test_journal import create


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.signed = []
        self.deleted = []
        self.fail = False

    async def sign_upload(self, path):
        self.signed.append(path)
        if self.fail:
            from app.core.errors import DomainError

            raise DomainError(503, "MEDIA_UNAVAILABLE", "Thử lại.", retryable=True)
        return {
            "uploadUrl": f"https://storage.example/storage/v1/object/upload/sign/journal-media/{path}?token=synthetic",
            "token": "synthetic",
            "resumableUrl": "https://storage.example/storage/v1/upload/resumable",
            "objectPath": path,
            "bucket": "journal-media",
        }

    async def info(self, path):
        return self.objects.get(path)

    async def sign_read(self, path):
        self.signed.append(path)
        return "https://storage.example/storage/v1/object/sign/temporary?token=synthetic"

    async def delete(self, path):
        if self.fail:
            from app.core.errors import DomainError

            raise DomainError(503, "MEDIA_UNAVAILABLE", "Thử lại.", retryable=True)
        self.deleted.append(path)
        self.objects.pop(path, None)


def media(**changes):
    return {"type": "image", "mimeType": "image/png", "sizeBytes": 100, **changes}


@pytest.mark.postgres
async def test_reservation_replay_owner_completion_and_private_access(clients):
    app, actors = clients
    (owner, uid), (other, _) = actors
    app.state.journal_storage = storage = FakeStorage()
    row = await create(owner)
    path = f"/api/v1/journal/entries/{row['id']}/media"
    headers = key()
    response = await owner.post(path, json=media(), headers=headers)
    assert response.status_code == 201, response.text
    reservation = response.json()
    assert reservation["media"]["status"] == "pending"
    assert reservation["objectPath"].startswith(f"users/{uid}/{row['id']}/image/")
    assert reservation["objectPath"].endswith(".png")
    assert (await owner.post(path, json=media(), headers=headers)).json() == reservation
    assert (await other.post(path, json=media(), headers=key())).status_code == 404
    attachment = f"{path}/{reservation['media']['id']}"
    assert (await owner.get(attachment + "/access")).status_code == 409
    assert (await other.get(attachment + "/access")).status_code == 404
    storage.objects[reservation["objectPath"]] = {"size": 100, "contentType": "image/png"}
    assert (await other.post(attachment + "/complete", json={}, headers=key())).status_code == 404
    ready = await owner.post(attachment + "/complete", json={}, headers=key())
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "ready"
    signed = (await owner.get(attachment + "/access")).json()
    assert signed["expiresIn"] == 60 and "token=" in signed["url"]
    assert (await other.request("DELETE", attachment, json={}, headers=key())).status_code == 404
    assert (await owner.request("DELETE", attachment, json={}, headers=key())).status_code == 200
    assert (await owner.get(attachment + "/access")).status_code == 404
    from app.modules.journal.models import JournalStorageDeletion

    async with app.state.database.sessions() as db:
        assert (await db.scalar(select(JournalStorageDeletion))).object_path == reservation[
            "objectPath"
        ]


@pytest.mark.postgres
@pytest.mark.parametrize(
    "payload",
    [
        media(mimeType="image/svg+xml"),
        media(sizeBytes=10485761),
        media(type="audio", mimeType="image/png"),
        media(type="video", mimeType="video/mp4", sizeBytes=52428801),
        media(sizeBytes=0),
        media(durationSeconds=-1),
    ],
)
async def test_invalid_media_never_gets_a_capability(clients, payload):
    app, actors = clients
    app.state.journal_storage = storage = FakeStorage()
    owner, _ = actors[0]
    row = await create(owner)
    response = await owner.post(
        f"/api/v1/journal/entries/{row['id']}/media", json=payload, headers=key()
    )
    assert response.status_code == 422, response.text
    assert storage.signed == []


@pytest.mark.postgres
async def test_sign_failure_reuses_reservation_and_mismatch_queues_cleanup(clients):
    app, actors = clients
    app.state.journal_storage = storage = FakeStorage()
    owner, _ = actors[0]
    row = await create(owner)
    path = f"/api/v1/journal/entries/{row['id']}/media"
    headers = key()
    storage.fail = True
    assert (await owner.post(path, json=media(), headers=headers)).status_code == 503
    storage.fail = False
    reservation = (await owner.post(path, json=media(), headers=headers)).json()
    assert len(set(storage.signed)) == 1
    storage.objects[reservation["objectPath"]] = {"size": 101, "contentType": "image/png"}
    failed = await owner.post(
        f"{path}/{reservation['media']['id']}/complete", json={}, headers=key()
    )
    assert failed.status_code == 422, failed.text
    detail = (await owner.get(f"/api/v1/journal/entries/{row['id']}")).json()
    assert detail["media"] == []
    from app.modules.journal.models import JournalStorageDeletion

    async with app.state.database.sessions() as db:
        assert await db.scalar(select(JournalStorageDeletion))


@pytest.mark.postgres
async def test_media_limit_and_unavailable_service(clients):
    app, actors = clients
    owner, _ = actors[0]
    row = await create(owner)
    path = f"/api/v1/journal/entries/{row['id']}/media"
    app.state.journal_storage = None
    assert (await owner.post(path, json=media(), headers=key())).status_code == 503
    app.state.journal_storage = FakeStorage()
    for _ in range(10):
        assert (await owner.post(path, json=media(), headers=key())).status_code == 201
    assert (await owner.post(path, json=media(), headers=key())).status_code == 422


@pytest.mark.postgres
async def test_cleanup_waits_for_capability_expiry_retries_and_reaps_pending(clients):
    from app.modules.journal.models import JournalMedia, JournalStorageDeletion
    from app.modules.journal.storage import process_storage_cleanup

    app, actors = clients
    owner, uid = actors[0]
    app.state.journal_storage = storage = FakeStorage()
    row = await create(owner)
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            [
                JournalStorageDeletion(object_path="users/recent", created_at=now()),
                JournalStorageDeletion(
                    object_path="users/old", created_at=now() - timedelta(hours=3)
                ),
                JournalMedia(
                    user_id=uid,
                    entry_id=UUID(row["id"]),
                    type="image",
                    object_path="users/abandoned",
                    mime_type="image/png",
                    size_bytes=100,
                    created_at=now() - timedelta(hours=25),
                ),
            ]
        )
    storage.fail = True
    await process_storage_cleanup(app)
    async with app.state.database.sessions() as db:
        jobs = (await db.scalars(select(JournalStorageDeletion))).all()
        assert any(j.object_path == "users/old" and j.attempts == 1 for j in jobs)
    storage.fail = False
    await process_storage_cleanup(app)
    assert "users/old" in storage.deleted and "users/recent" not in storage.deleted
    assert (
        "users/abandoned" not in storage.deleted
    )  # newly queued; delay also covers refreshed capability
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(JournalMedia)) is None
        assert {
            r.object_path for r in (await db.scalars(select(JournalStorageDeletion))).all()
        } == {"users/recent", "users/abandoned"}


async def test_storage_http_adapter_uses_only_scoped_private_operations():
    from app.core.config import Settings
    from app.modules.journal.storage import SupabaseJournalStorage

    calls = []

    def provider(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer synthetic-server-only"
        path = request.url.path
        if "/bucket/" in path:
            return httpx.Response(200, json={"public": False})
        if "/upload/sign/" in path:
            return httpx.Response(
                200, json={"url": path.replace("/storage/v1", "") + "?token=upload-token"}
            )
        if "/object/info/" in path:
            return httpx.Response(
                200, json={"size": 100, "content_type": "image/png", "metadata": None}
            )
        if "/object/sign/" in path:
            return httpx.Response(
                200, json={"signedURL": "/object/sign/journal-media/users/test?token=read-token"}
            )
        return httpx.Response(200, json=[])

    settings = Settings(
        _env_file=None,
        supabase_url="https://project.supabase.co",
        journal_storage_key="synthetic-server-only",
    )
    adapter = SupabaseJournalStorage(settings, transport=httpx.MockTransport(provider))
    upload = await adapter.sign_upload("users/test.png")
    assert upload["token"] == "upload-token"
    assert (
        upload["resumableUrl"]
        == "https://project.storage.supabase.co/storage/v1/upload/resumable/sign"
    )
    assert (await adapter.info("users/test.png")) == {"size": 100, "contentType": "image/png"}
    assert "read-token" in await adapter.sign_read("users/test.png")
    await adapter.delete("users/test.png")
    assert calls[-1].method == "DELETE"
    assert b'"prefixes":["users/test.png"]' in calls[-1].content
    assert all("public" not in str(call.url) for call in calls)


@pytest.mark.parametrize("custom", [None, {}, {"size": 100, "content_type": "image/png"}])
async def test_storage_info_ignores_user_controlled_custom_metadata(custom):
    from app.core.config import Settings
    from app.modules.journal.storage import SupabaseJournalStorage

    adapter = SupabaseJournalStorage(
        Settings(
            _env_file=None,
            supabase_url="https://project.supabase.co",
            journal_storage_key="synthetic",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"size": 50000000, "content_type": "video/mp4", "metadata": custom}
            )
        ),
    )
    assert await adapter.info("users/test") == {"size": 50000000, "contentType": "video/mp4"}


def test_storage_csp_uses_exact_origin_only():
    from app.main import content_security_policy

    value = content_security_policy(storage_origin="https://project.supabase.co")
    assert "https://project.supabase.co" in value
    assert "https://project.storage.supabase.co" in value
    assert "*.supabase.co" not in value
    assert "supabase.co" not in content_security_policy()


async def test_storage_missing_object_uses_provider_not_found_code_with_http400():
    from app.core.config import Settings
    from app.modules.journal.storage import SupabaseJournalStorage

    adapter = SupabaseJournalStorage(
        Settings(
            _env_file=None,
            supabase_url="https://project.supabase.co",
            journal_storage_key="synthetic",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                400, json={"statusCode": "404", "error": "not_found", "message": "Object not found"}
            )
        ),
    )
    assert await adapter.info("verification/missing") is None
