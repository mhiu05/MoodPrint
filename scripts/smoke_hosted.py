"""Explicit synthetic Phase 0 smoke; never run from automatic pytest.

Requires migrated target and a restricted moodprint_api DATABASE_URL. Outputs
only checkpoint names; upstream errors, tokens and connection strings are hidden.
"""

import argparse
import asyncio
import secrets
from uuid import uuid4

import httpx
from app.main import create_app
from app.modules.evidence.keys import original_key
from db.safety import ROOT, is_generated_runtime_url, validate_hosted_target
from dotenv import dotenv_values
from moodprint_shared.config import AppConfig
from moodprint_shared.env import EnvSettings


async def run() -> None:
    values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value}
    admin_url = values.get("SUPABASE_DB_URL", "")
    runtime_url = values.get("DATABASE_URL", "")
    validate_hosted_target(values.get("SUPABASE_URL", ""), admin_url)
    if not is_generated_runtime_url(runtime_url):
        raise ValueError("DATABASE_URL must be provisioned as moodprint_api before hosted smoke")
    settings = EnvSettings(**values)
    app, users, storage_keys = create_app(settings), [], []
    base = settings.supabase_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as upstream:
        admin_headers = {
            "apikey": settings.supabase_secret_key.get_secret_value(),
            "Authorization": "Bearer " + settings.supabase_secret_key.get_secret_value(),
        }
        public_headers = {"apikey": settings.supabase_publishable_key}
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://smoke"
                ) as api:
                    if (await api.get("/ready")).status_code != 200:
                        raise RuntimeError("Hosted readiness failed")
                    print("VERIFIED readiness")
                    tokens = []
                    for _ in range(2):
                        email, password = f"smoke+{uuid4()}@example.test", secrets.token_urlsafe(24)
                        created = await upstream.post(
                            base + "/auth/v1/admin/users",
                            headers=admin_headers,
                            json={
                                "email": email,
                                "password": password,
                                "email_confirm": True,
                                "user_metadata": {
                                    "nickname": "Synthetic smoke",
                                    "age_band": "14-17",
                                },
                            },
                        )
                        if created.status_code not in (200, 201):
                            raise RuntimeError("Synthetic Auth user creation failed")
                        user_id = created.json()["id"]
                        users.append(user_id)
                        signed = await upstream.post(
                            base + "/auth/v1/token?grant_type=password",
                            headers=public_headers,
                            json={"email": email, "password": password},
                        )
                        if signed.status_code != 200:
                            raise RuntimeError("Synthetic Auth sign-in failed")
                        tokens.append(signed.json()["access_token"])
                    auth_a, auth_b = [{"Authorization": "Bearer " + token} for token in tokens]
                    profile = await api.get("/v1/me", headers=auth_a)
                    if (
                        profile.status_code != 200
                        or profile.json()["nickname"] != "Synthetic smoke"
                    ):
                        raise RuntimeError("Hosted profile persistence failed")
                    created = await api.post(
                        "/v1/memories",
                        headers=auth_a,
                        json={"category": "preference", "content": "Synthetic smoke preference"},
                    )
                    if created.status_code != 200:
                        raise RuntimeError("Hosted memory creation failed")
                    memory_id = created.json()["id"]
                    if (
                        await api.patch(
                            f"/v1/memories/{memory_id}",
                            headers=auth_b,
                            json={"content": "Forbidden synthetic update"},
                        )
                    ).status_code != 404:
                        raise RuntimeError("Hosted cross-user isolation failed")
                    if (
                        await api.delete(f"/v1/memories/{memory_id}", headers=auth_a)
                    ).status_code != 204:
                        raise RuntimeError("Hosted memory deletion failed")
                    print("VERIFIED authenticated profile, memory lifecycle, cross-user isolation")
                    from uuid import UUID

                    key = original_key(UUID(users[0]), uuid4(), "application/octet-stream")
                    storage_keys.append(key)
                    gateway = app.state.storage
                    upload = await gateway.create_upload_token(key)
                    response = await upstream.put(
                        base + "/storage/v1/object/upload/sign/incident-evidence/" + key,
                        params={"token": upload.token},
                        content=b"S" * 1024,
                        headers={"Content-Type": "application/octet-stream"},
                    )
                    if response.status_code not in (200, 201):
                        raise RuntimeError("Hosted signed upload failed")
                    info = await gateway.object_info(key)
                    if info is None or info.byte_size != 1024:
                        raise RuntimeError("Hosted storage metadata failed")
                    download = await gateway.create_download_url(
                        key, 120, attachment_name="synthetic.bin"
                    )
                    if (await upstream.get(download)).content != b"S" * 1024:
                        raise RuntimeError("Hosted signed download failed")
                    await gateway.delete(storage_keys)
                    storage_keys.clear()
                    print("VERIFIED private signed upload/download")
        finally:
            if storage_keys:
                from app.infrastructure.storage_gateway import StorageGateway

                await StorageGateway(settings, AppConfig(), upstream).delete(storage_keys)
            for user_id in users:
                response = await upstream.delete(
                    base + "/auth/v1/admin/users/" + user_id, headers=admin_headers
                )
                if response.status_code not in (200, 204, 404):
                    raise RuntimeError("Synthetic user cleanup failed; inspect hosted smoke users")
            if users:
                print("VERIFIED synthetic cleanup completed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("0",), default="0")
    parser.parse_args()
    try:
        asyncio.run(run())
    except ValueError as error:
        print(str(error))
        return 1
    except Exception:
        print("FAILED hosted smoke; connection, credential and upstream details suppressed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
