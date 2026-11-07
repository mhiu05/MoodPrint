"""Crash recovery uses durable state; no database transaction spans Storage calls."""

from uuid import uuid4

import pytest
from app.core.errors import ApiError
from app.core.uow import user_uow
from app.infrastructure.storage_gateway import ObjectInfo
from app.modules.evidence.schemas import UploadCreate
from app.modules.evidence.service import EvidenceService
from app.modules.profiles.service import ProfileService
from sqlalchemy import text

from backend.tests.integration.test_phase1_domains import Files, case

pytestmark = pytest.mark.integration


async def test_purger_retries_and_preserves_failed_upload_metadata(db_engine, identities):
    from app.jobs.evidence import purge_once

    a = identities[0]
    storage = Files()
    service = EvidenceService(db_engine, storage)
    upload = await service.init_upload(a, UploadCreate(id=uuid4(), filename="x", byte_size=10))
    storage.objects[upload.upload.object_name] = ObjectInfo(11, "text/plain", "etag")
    with pytest.raises(ApiError):
        await service.complete(a, upload.evidence.id)
    assert await purge_once(db_engine, storage) == 1
    assert storage.objects == {}
    assert (await service.get(a, upload.evidence.id)).upload_status == "failed"
    assert await purge_once(db_engine, storage) == 0


class AuthDeletion:
    def __init__(self):
        self.fail = True

    async def require_live_user(self, auth, token):
        return None

    async def delete_user(self, auth):
        if self.fail:
            raise ApiError("upstream_error", "Auth temporarily unavailable", 502)


async def test_account_deletion_partial_failure_resumable(db_engine, identities):
    a = identities[0]
    storage = Files()
    provider = AuthDeletion()
    service = ProfileService(db_engine, provider)
    await service.get(a)
    await case(db_engine, a)
    evidence = EvidenceService(db_engine, storage)
    upload = await evidence.init_upload(a, UploadCreate(id=uuid4(), filename="x", byte_size=10))
    storage.objects[upload.upload.object_name] = ObjectInfo(10, "text/plain", "etag")
    await evidence.complete(a, upload.evidence.id)
    with pytest.raises(ApiError):
        await service.delete_account(a, "test", storage)
    assert storage.objects == {}
    with pytest.raises(ApiError) as blocked:
        async with user_uow(db_engine, a):
            pytest.fail("An unfinished deletion must block ordinary account access")
    assert blocked.value.code == "account_deleting"
    from app.core.uow import account_deletion_scope

    with account_deletion_scope(a):
        async with user_uow(db_engine, a) as uow:
            assert (
                await uow.session.scalar(
                    text("SELECT count(*) FROM app.cases WHERE owner_id=:owner"),
                    {"owner": a.user_id},
                )
                == 0
            )
            assert (
                await uow.session.scalar(
                    text("SELECT count(*) FROM app.evidence_items WHERE owner_id=:owner"),
                    {"owner": a.user_id},
                )
                == 0
            )
    provider.fail = False
    await service.delete_account(a, "test", storage)


async def test_deleted_upload_still_counts_hourly_rate(db_engine, identities):
    from moodprint_shared.config import AppConfig, EvidenceConfig

    storage = Files()
    service = EvidenceService(
        db_engine, storage, AppConfig(evidence=EvidenceConfig(upload_rate_per_hour=1))
    )
    auth = identities[0]
    initial = await service.init_upload(auth, UploadCreate(id=uuid4(), filename="one", byte_size=8))
    await service.delete(auth, initial.evidence.id)
    with pytest.raises(ApiError) as limited:
        await service.init_upload(auth, UploadCreate(id=uuid4(), filename="two", byte_size=8))
    assert limited.value.code == "rate_limited"
