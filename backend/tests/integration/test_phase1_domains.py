"""Owner boundaries and durable domain transitions on the local PostgreSQL stack."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.errors import ApiError
from app.core.uow import user_uow
from app.infrastructure.storage_gateway import ObjectInfo, SignedUpload
from safevoice_shared.config import AppConfig, EvidenceConfig
from safevoice_shared.contracts.errors import NotFound, QuotaExceeded, VersionConflict
from sqlalchemy import text

pytestmark = pytest.mark.integration


class Files:
    def __init__(self):
        self.objects = {}
        self.fail_delete = False

    async def create_upload_token(self, key):
        return SignedUpload(
            "https://files.invalid/resumable/sign",
            "capability",
            6291456,
            key,
            "incident-evidence",
            datetime.now(UTC) + timedelta(hours=2),
        )

    async def object_info(self, key):
        return self.objects.get(key)

    async def create_download_url(self, key, ttl_s, *, attachment_name):
        assert key in self.objects
        return "https://files.invalid/read?download=" + (attachment_name or "")

    async def delete(self, keys):
        if self.fail_delete:
            raise ApiError("upstream_error", "Thử lại sau.", 502)
        for key in keys:
            self.objects.pop(key, None)


async def case(engine, auth):
    id = uuid4()
    async with user_uow(engine, auth) as uow:
        await uow.session.execute(
            text("""INSERT INTO app.cases
          (id,owner_id,title,template,perspective,summary,status)
          VALUES(:id,:owner,'Synthetic case','TPL-FREE','self','Synthetic summary','active')"""),
            {"id": id, "owner": auth.user_id},
        )
    return id


async def test_contacts_crud_idempotency_and_owner_isolation(db_engine, identities):
    from app.modules.contacts.schemas import ContactCreate, ContactPatch
    from app.modules.contacts.service import ContactService

    a, b = identities
    service = ContactService(db_engine)
    data = ContactCreate(id=uuid4(), label="Synthetic Teacher", role="Teacher")
    first = await service.create(a, data)
    assert (await service.create(a, data)).id == first.id
    assert (await service.list(a)).items[0].label == "Synthetic Teacher"
    assert (await service.list(b)).items == []
    with pytest.raises(NotFound):
        await service.patch(b, first.id, ContactPatch(label="Other teacher"))
    updated = await service.patch(a, first.id, ContactPatch(role="Counsellor"))
    assert updated.role == "Counsellor"
    await service.delete(a, first.id)
    assert (await service.list(a)).items == []


async def test_support_version_and_article_state_owner_scope(db_engine, identities):
    from app.modules.knowledge_state.schemas import ArticleStatePut
    from app.modules.knowledge_state.service import KnowledgeStateService
    from app.modules.support.schemas import DraftCreate, DraftPatch
    from app.modules.support.service import SupportService

    a, b = identities
    service = SupportService(db_engine)
    data = DraftCreate(id=uuid4(), recipient_type="teacher", content="Synthetic message")
    created = await service.create(a, data)
    updated = await service.patch(a, created.id, DraftPatch(version=1, status="prepared"))
    assert updated.version == 2 and updated.content == "Synthetic message"
    with pytest.raises(VersionConflict):
        await service.patch(a, created.id, DraftPatch(version=1, content="stale"))
    with pytest.raises(NotFound):
        await service.get(b, created.id)
    states = KnowledgeStateService(db_engine)
    state = await states.put(
        a, "article-01", ArticleStatePut(bookmarked=True, read_at=datetime.now(UTC))
    )
    assert state.bookmarked and state.read_at
    assert (await states.list(b)).items == []
    assert len((await states.list(a)).items) == 1


async def test_evidence_init_complete_review_and_download(db_engine, identities):
    from app.modules.evidence.schemas import EvidencePatch, UploadCreate
    from app.modules.evidence.service import EvidenceService

    a, b = identities
    storage = Files()
    service = EvidenceService(db_engine, storage)
    data = UploadCreate(id=uuid4(), filename="private name.png", mime_type="image/png", byte_size=8)
    pending = await service.init_upload(a, data)
    assert pending.evidence.upload_status == "pending"
    assert "private name" not in pending.upload.object_name
    assert (await service.init_upload(a, data)).evidence.id == data.id
    with pytest.raises(ApiError):
        await service.complete(a, data.id)
    storage.objects[pending.upload.object_name] = ObjectInfo(8, "image/png", "etag-1")
    complete = await service.complete(a, data.id)
    assert complete.upload_status == "uploaded" and complete.byte_size == 8
    assert (await service.complete(a, data.id)) == complete
    with pytest.raises(NotFound):
        await service.get(b, data.id)
    edited = await service.patch(
        a, data.id, EvidencePatch(user_edited_text="Corrected", review_status="corrected")
    )
    assert edited.original_filename == "private name.png" and edited.user_edited_text == "Corrected"
    assert (await service.open_read_url(a, data.id, "user_preview")).url.startswith(
        "https://files.invalid/"
    )


async def test_evidence_reserves_quota_and_size_mismatch_fails(db_engine, identities):
    from app.modules.evidence.schemas import UploadCreate
    from app.modules.evidence.service import EvidenceService

    a = identities[0]
    storage = Files()
    service = EvidenceService(
        db_engine, storage, AppConfig(evidence=EvidenceConfig(user_quota_bytes=10))
    )
    pending = await service.init_upload(a, UploadCreate(id=uuid4(), filename="x", byte_size=8))
    with pytest.raises(QuotaExceeded):
        await service.init_upload(a, UploadCreate(id=uuid4(), filename="y", byte_size=8))
    storage.objects[pending.upload.object_name] = ObjectInfo(9, "text/plain", "etag")
    with pytest.raises(ApiError):
        await service.complete(a, pending.evidence.id)
    assert (await service.get(a, pending.evidence.id)).upload_status == "failed"


async def test_evidence_delete_recovers_after_storage_failure(db_engine, identities):
    from app.modules.evidence.schemas import NoteCreate, UploadCreate
    from app.modules.evidence.service import EvidenceService

    a = identities[0]
    storage = Files()
    service = EvidenceService(db_engine, storage)
    pending = await service.init_upload(a, UploadCreate(id=uuid4(), filename="x", byte_size=8))
    storage.objects[pending.upload.object_name] = ObjectInfo(8, "text/plain", "etag")
    await service.complete(a, pending.evidence.id)
    storage.fail_delete = True
    with pytest.raises(ApiError):
        await service.delete(a, pending.evidence.id)
    assert (await service.get(a, pending.evidence.id)).upload_status == "deleting"
    storage.fail_delete = False
    await service.delete(a, pending.evidence.id)
    assert storage.objects == {}
    with pytest.raises(NotFound):
        await service.get(a, pending.evidence.id)
    note = await service.create_note(a, NoteCreate(id=uuid4(), original_text="Original note"))
    assert note.kind == "text_note" and note.original_text == "Original note"
    assert note.upload_status == "uploaded"


async def test_share_snapshot_scope_hash_and_withdrawal(db_engine, identities):
    from app.modules.sharing.schemas import ShareCreate, ShareSubmit
    from app.modules.sharing.service import SharingService
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.tests.integration.conftest import local_value

    a, b = identities
    case_id = await case(db_engine, a)
    school = uuid4()
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        async with admin.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app.schools(id,name,verification_status) VALUES(:id,'Synthetic school','verified')"
                ),
                {"id": school},
            )
            await conn.execute(
                text(
                    "INSERT INTO app.school_memberships(school_id,user_id,role,status) VALUES(:id,:user,'staff','active')"
                ),
                {"id": school, "user": b.user_id},
            )
        service = SharingService(db_engine, Files())
        draft = await service.create(
            a, ShareCreate(id=uuid4(), case_id=case_id, school_id=school, shared_fields=["summary"])
        )
        assert (await service.school_list(b, school)).items == []
        preview = await service.preview(a, draft.id)
        with pytest.raises(VersionConflict):
            await service.submit(
                a,
                draft.id,
                ShareSubmit(confirmed=True, confirmation_version="v1", preview_hash="stale"),
            )
        submitted = await service.submit(
            a,
            draft.id,
            ShareSubmit(
                confirmed=True, confirmation_version="v1", preview_hash=preview.preview_hash
            ),
        )
        assert submitted.snapshot["fields"] == {"summary": "Synthetic summary"}
        assert (await service.school_get(b, school, draft.id)).snapshot == submitted.snapshot
        async with user_uow(db_engine, a) as uow:
            await uow.session.execute(
                text("UPDATE app.cases SET summary='Changed later' WHERE id=:id"), {"id": case_id}
            )
        assert (await service.school_get(b, school, draft.id)).snapshot["fields"][
            "summary"
        ] == "Synthetic summary"
        await service.withdraw(a, draft.id)
        with pytest.raises(NotFound):
            await service.school_get(b, school, draft.id)
    finally:
        async with admin.begin() as conn:
            await conn.execute(
                text("DELETE FROM app.case_shares WHERE school_id=:id"), {"id": school}
            )
            await conn.execute(
                text("DELETE FROM app.school_memberships WHERE school_id=:id"), {"id": school}
            )
            await conn.execute(text("DELETE FROM app.schools WHERE id=:id"), {"id": school})
        await admin.dispose()
