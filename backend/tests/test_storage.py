from uuid import UUID

import httpx
import pytest
from app.infrastructure.storage_gateway import StorageGateway
from app.modules.evidence.keys import derived_key, original_key
from moodprint_shared.config import AppConfig

OWNER = UUID("00000000-0000-0000-0000-000000000001")
EVIDENCE = UUID("00000000-0000-0000-0000-000000000002")


def test_keys_never_contain_filename():
    key = original_key(OWNER, EVIDENCE, "image/png")
    assert key.startswith(f"users/{OWNER}/originals/{EVIDENCE}/")
    assert key.endswith(".png")
    assert original_key(OWNER, EVIDENCE, "image/png") != key


def test_unknown_mime_has_no_extension():
    key = original_key(OWNER, EVIDENCE, "anything/../private.txt")
    assert "." not in key.rsplit("/", 1)[1]


def test_original_and_derived_prefixes_disjoint():
    key = derived_key(OWNER, EVIDENCE, "thumbnail", EVIDENCE, "png")
    assert "/derived/" in key and "/originals/" not in key
    with pytest.raises(ValueError):
        derived_key(OWNER, EVIDENCE, "../../bad", EVIDENCE, "png")


async def test_signed_upload_never_uses_upsert(settings):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, json={"token": "signed-test-token", "url": "/object/upload/sign/test"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = StorageGateway(settings, AppConfig(), client)
        result = await gateway.create_upload_token(original_key(OWNER, EVIDENCE, None))
    assert result.token == "signed-test-token"
    assert all(r.headers.get("x-upsert") != "true" for r in requests)


async def test_storage_error_hides_upstream_body(settings):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(500, text="sensitive-upstream-detail")
        )
    ) as client:
        gateway = StorageGateway(settings, AppConfig(), client)
        with pytest.raises(Exception) as error:
            await gateway.create_upload_token(original_key(OWNER, EVIDENCE, None))
    assert "sensitive-upstream-detail" not in str(error.value)


async def test_object_info_maps_storage_snake_case_fields(settings):
    # Shape observed from local Storage v1.84.19, including metadata=null.
    payload = {
        "size": 23,
        "content_type": "application/octet-stream",
        "etag": "actual-etag",
        "metadata": None,
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        gateway = StorageGateway(settings, AppConfig(), client)
        info = await gateway.object_info(original_key(OWNER, EVIDENCE, None))
    assert info.byte_size == 23
    assert info.mime_type == "application/octet-stream"
    assert info.etag == "actual-etag"
