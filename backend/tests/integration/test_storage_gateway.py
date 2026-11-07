from uuid import uuid4

import httpx
import pytest
from app.infrastructure.storage_gateway import StorageGateway
from app.modules.evidence.keys import original_key
from moodprint_shared.config import AppConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_auth_flow import local_settings as local_settings

pytestmark = pytest.mark.integration


async def test_bucket_is_private_and_has_no_limits():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT public,file_size_limit,allowed_mime_types FROM storage.buckets WHERE id='incident-evidence'"
                    )
                )
            ).one()
        assert row.public is False
        assert row.file_size_limit is None
        assert row.allowed_mime_types is None
    finally:
        await engine.dispose()


async def test_gateway_missing_object_is_none_and_upload_is_scoped(local_settings):
    key = original_key(uuid4(), uuid4(), "application/octet-stream")
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        assert await gateway.object_info(key) is None
        upload = await gateway.create_upload_token(key)
        assert upload.object_name == key
        assert upload.bucket_name == "incident-evidence"
        assert upload.chunk_size == 6 * 1024**2
        assert upload.url == local_settings.supabase_url + "/storage/v1/upload/resumable/sign"
        assert upload.token
