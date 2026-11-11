"""Exercise the real Storage signed-upload flow, including HTTP TUS resume."""

import asyncio
import base64
import json
import subprocess
import time
import tomllib
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from app.infrastructure.storage_gateway import StorageGateway
from app.modules.evidence.keys import original_key
from safevoice_shared.config import AppConfig

from backend.tests.integration.test_auth_flow import (
    auth_users as auth_users,
)
from backend.tests.integration.test_auth_flow import (
    checked,
)
from backend.tests.integration.test_auth_flow import (
    local_settings as local_settings,
)

pytestmark = pytest.mark.integration


def local_storage_signing_secret() -> str:
    """Use only the local test container; never return signing material to tool output."""
    config = tomllib.loads(
        (Path(__file__).resolve().parents[3] / "supabase/config.toml").read_text(encoding="utf-8")
    )
    result = subprocess.run(
        ["docker", "inspect", f"supabase_storage_{config['project_id']}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        pytest.fail("Local Storage container inspection failed; expiry spike requires local Docker")
    container = json.loads(result.stdout)[0]
    environment = dict(item.split("=", 1) for item in container["Config"]["Env"])
    value = environment.get("AUTH_JWT_SECRET")
    if not value:
        pytest.fail("Local Storage signing configuration unavailable for bounded expiry spike")
    return value


def tus_headers(settings, upload, *, offset=None):
    headers = {
        "Tus-Resumable": "1.0.0",
        "x-signature": upload.token,
        "apikey": settings.supabase_publishable_key,
    }
    if offset is not None:
        headers.update(
            {"Upload-Offset": str(offset), "Content-Type": "application/offset+octet-stream"}
        )
    return headers


async def start_tus(client, settings, upload, size, *, object_name=None):
    metadata = {
        "bucketName": upload.bucket_name,
        "objectName": object_name or upload.object_name,
        "contentType": "application/octet-stream",
        "cacheControl": "0",
    }
    headers = tus_headers(settings, upload)
    headers["Upload-Length"] = str(size)
    headers["Upload-Metadata"] = ",".join(
        f"{key} {base64.b64encode(value.encode()).decode()}" for key, value in metadata.items()
    )
    response = await client.post(upload.url, headers=headers)
    return response


def upload_location(settings, response):
    location = urljoin(settings.supabase_url, response.headers["Location"])
    expected = urlsplit(settings.supabase_url)
    observed = urlsplit(location)
    assert (observed.scheme, observed.hostname, observed.port) == (
        expected.scheme,
        expected.hostname,
        expected.port,
    )
    return location


async def append_tus(client, settings, upload, location, data, offset):
    response = await client.patch(
        location, content=data, headers=tus_headers(settings, upload, offset=offset)
    )
    checked(response, {204}, "append TUS chunk")
    assert int(response.headers["Upload-Offset"]) == offset + len(data)


async def upload_small(client, settings, gateway, key):
    upload = await gateway.create_upload_token(key)
    data = b"synthetic-storage-fixture"
    response = await start_tus(client, settings, upload, len(data))
    checked(response, {201}, "create signed TUS upload")
    location = upload_location(settings, response)
    await append_tus(client, settings, upload, location, data, 0)
    return upload, data


async def test_signed_token_uploads_small_file(local_settings):
    key = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            _, data = await upload_small(client, local_settings, gateway, key)
            info = await gateway.object_info(key)
            assert info is not None and info.byte_size == len(data)
        finally:
            await gateway.delete([key])


async def test_signed_tus_requires_capability_on_post_head_and_patch(local_settings):
    key = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            upload = await gateway.create_upload_token(key)
            without_capability = replace(upload, token="")
            response = await start_tus(client, local_settings, without_capability, 1)
            assert response.status_code >= 400
            response = await start_tus(client, local_settings, upload, 1)
            checked(response, {201}, "create authorized signed upload")
            location = upload_location(local_settings, response)
            response = await client.head(
                location, headers=tus_headers(local_settings, without_capability)
            )
            assert response.status_code >= 400
            response = await client.patch(
                location,
                content=b"X",
                headers=tus_headers(local_settings, without_capability, offset=0),
            )
            assert response.status_code >= 400
            await append_tus(client, local_settings, upload, location, b"S", 0)
            url = await gateway.create_download_url(key, 120, attachment_name=None)
            response = await client.get(url)
            checked(response, {200}, "read object after unauthorized chunk attempt")
            assert response.content == b"S"
        finally:
            await gateway.delete([key])


async def test_tus_resume_after_interruption_20_mib(local_settings):
    key = original_key(uuid4(), uuid4(), None)
    size, chunk_size = 20 * 1024**2, 6 * 1024**2
    data = b"S" * size
    async with httpx.AsyncClient(timeout=60) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            upload = await gateway.create_upload_token(key)
            response = await start_tus(client, local_settings, upload, size)
            checked(response, {201}, "start 20 MiB signed TUS upload")
            location = upload_location(local_settings, response)
            await append_tus(client, local_settings, upload, location, data[:chunk_size], 0)
            # A fresh HTTP client reproduces loss of the first client's connection state.
            async with httpx.AsyncClient(timeout=60) as resumed:
                response = await resumed.head(location, headers=tus_headers(local_settings, upload))
                checked(response, {200, 204}, "recover TUS upload offset")
                offset = int(response.headers["Upload-Offset"])
                assert offset == chunk_size
                while offset < size:
                    block = data[offset : offset + chunk_size]
                    await append_tus(resumed, local_settings, upload, location, block, offset)
                    offset += len(block)
            info = await gateway.object_info(key)
            assert info is not None and info.byte_size == size
            url = await gateway.create_download_url(key, 120, attachment_name="synthetic.bin")
            response = await client.get(url)
            checked(response, {200}, "read resumed object through signed URL")
            assert response.content == data
        finally:
            await gateway.delete([key])


async def test_user_a_token_not_usable_on_other_key(local_settings):
    first = original_key(uuid4(), uuid4(), None)
    second = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            upload = await gateway.create_upload_token(first)
            response = await start_tus(client, local_settings, upload, 1, object_name=second)
            assert response.status_code >= 400
        finally:
            await gateway.delete([first, second])


async def test_cannot_overwrite_existing_object(local_settings):
    key = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            upload, data = await upload_small(client, local_settings, gateway, key)
            # Reusing the signed capability never grants object replacement.
            response = await start_tus(client, local_settings, upload, 1)
            if response.status_code == 201:
                location = upload_location(local_settings, response)
                response = await client.patch(
                    location, content=b"X", headers=tus_headers(local_settings, upload, offset=0)
                )
            assert response.status_code >= 400
            url = await gateway.create_download_url(key, 120, attachment_name=None)
            response = await client.get(url)
            assert response.content == data
        finally:
            await gateway.delete([key])


async def test_user_jwt_cannot_read_list_or_write_and_anon_cannot_read(local_settings, auth_users):
    user = auth_users[0]
    key = original_key(user.user_id, uuid4(), None)
    bucket = AppConfig().evidence.bucket
    object_path = f"/storage/v1/object/authenticated/{bucket}/{quote(key, safe='/')}"
    headers = {
        "apikey": local_settings.supabase_publishable_key,
        "Authorization": f"Bearer {user.token}",
    }
    async with httpx.AsyncClient(base_url=local_settings.supabase_url, timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            await upload_small(client, local_settings, gateway, key)
            response = await client.get(object_path, headers=headers)
            assert response.status_code >= 400
            response = await client.post(
                f"/storage/v1/object/list/{bucket}",
                headers=headers,
                json={"prefix": f"users/{user.user_id}", "limit": 100},
            )
            assert response.status_code >= 400 or response.json() == []
            response = await client.post(
                f"/storage/v1/object/{bucket}/{quote(key + '-denied', safe='/')}",
                headers={**headers, "Content-Type": "application/octet-stream"},
                content=b"X",
            )
            assert response.status_code >= 400
            response = await client.get(
                object_path, headers={"apikey": local_settings.supabase_publishable_key}
            )
            assert response.status_code >= 400
        finally:
            await gateway.delete([key, key + "-denied"])


async def test_download_url_expires(local_settings):
    """An expired signed download URL is refused by Storage.

    The first version waited out a real 1 s window: the "live" read had to finish within one second of
    signing, so under load it failed *before* the expiry check was even reached (CC-P3-003). Expiry is
    now exercised without racing the clock: the issued capability is re-signed locally (the same
    technique as the TUS expiry test below) once with an expiry in the past and once, as a control,
    with an expiry well in the future. Only the expiry differs, so a refusal can only be the expiry.
    """
    key = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            await upload_small(client, local_settings, gateway, key)
            url = await gateway.create_download_url(key, 60, attachment_name=None)
            response = await client.get(url)
            checked(response, {200}, "read live signed download URL")

            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query))
            token = query["token"]
            assert jwt.get_unverified_header(token)["alg"] == "HS256", (
                "Update the expiry test for the local signing algorithm"
            )
            claims = jwt.decode(token, options={"verify_signature": False})
            secret = await asyncio.to_thread(local_storage_signing_secret)

            def resigned(expiry: int) -> str:
                signed = jwt.encode({**claims, "exp": expiry}, secret, algorithm="HS256")
                return urlunsplit(parts._replace(query=urlencode({**query, "token": signed})))

            now = int(time.time())
            control = await client.get(resigned(now + 300), headers={"Cache-Control": "no-cache"})
            checked(control, {200}, "control: same capability re-signed with a future expiry")
            expired = await client.get(resigned(now - 60), headers={"Cache-Control": "no-cache"})
            assert expired.status_code >= 400, "Expired signed download URL remained authorized"
            assert expired.content != control.content
        finally:
            await gateway.delete([key])


async def test_signed_upload_token_has_two_hour_lifetime(local_settings):
    key = original_key(uuid4(), uuid4(), None)
    async with httpx.AsyncClient(timeout=30) as client:
        upload = await StorageGateway(local_settings, AppConfig(), client).create_upload_token(key)
        claims = jwt.decode(upload.token, options={"verify_signature": False})
        assert 7100 <= claims["exp"] - time.time() <= 7300


async def test_tus_expired_capability_refreshed_then_resumes_same_upload(local_settings):
    """Exercise actual expiry using a locally re-signed 15-second capability, not a 2h wait."""
    key = original_key(uuid4(), uuid4(), None)
    data = b"R" * (20 * 1024**2)
    chunk_size = 6 * 1024**2
    async with httpx.AsyncClient(timeout=60) as client:
        gateway = StorageGateway(local_settings, AppConfig(), client)
        try:
            issued = await gateway.create_upload_token(key)
            header = jwt.get_unverified_header(issued.token)
            assert header["alg"] == "HS256", (
                "Update bounded expiry spike for local signing algorithm"
            )
            claims = jwt.decode(issued.token, options={"verify_signature": False})
            expiry = int(time.time()) + 15
            secret = await asyncio.to_thread(local_storage_signing_secret)
            shortened = replace(
                issued,
                token=jwt.encode({**claims, "exp": expiry}, secret, algorithm="HS256"),
            )
            del secret
            response = await start_tus(client, local_settings, shortened, len(data))
            checked(response, {201}, "start short-lived signed TUS upload")
            location = upload_location(local_settings, response)
            await append_tus(client, local_settings, shortened, location, data[:chunk_size], 0)
            await asyncio.sleep(max(0, expiry - time.time() + 1))
            expired = await client.head(location, headers=tus_headers(local_settings, shortened))
            assert expired.status_code >= 400, "Expired upload capability remained authorized"
            fresh = await gateway.create_upload_token(key)
            async with httpx.AsyncClient(timeout=60) as resumed:
                response = await resumed.head(location, headers=tus_headers(local_settings, fresh))
                checked(response, {200, 204}, "resume same upload with refreshed capability")
                offset = int(response.headers["Upload-Offset"])
                assert offset == chunk_size
                while offset < len(data):
                    block = data[offset : offset + chunk_size]
                    await append_tus(resumed, local_settings, fresh, location, block, offset)
                    offset += len(block)
            info = await gateway.object_info(key)
            assert info is not None and info.byte_size == len(data)
            url = await gateway.create_download_url(key, 120, attachment_name=None)
            response = await client.get(url)
            checked(response, {200}, "read object resumed after capability expiry")
            assert response.content == data
        finally:
            await gateway.delete([key])
