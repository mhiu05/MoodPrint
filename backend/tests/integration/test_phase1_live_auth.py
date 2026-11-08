"""Real local Auth/Storage account deletion, plus the documented capability TTL limit."""

import secrets
from uuid import UUID, uuid4

import httpx
import pytest
from app.core.auth import JwtVerifier
from app.infrastructure.auth_admin import AuthAdmin
from app.infrastructure.storage_gateway import StorageGateway
from app.main import create_app
from app.modules.evidence.schemas import UploadInfo
from moodprint_shared.config import AppConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_auth_flow import local_settings as local_settings
from backend.tests.integration.test_storage_access import append_tus, start_tus, upload_location

pytestmark = pytest.mark.integration


async def test_real_account_delete_cleans_tracked_data_and_stale_jwt_is_rejected(
    local_settings, db_engine
):
    cfg = AppConfig()
    user_id = None
    keys = []
    admin_db = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    async with httpx.AsyncClient(timeout=30) as external:
        secret = local_settings.supabase_secret_key.get_secret_value()
        headers = {"apikey": secret, "Authorization": "Bearer " + secret}
        gateway = StorageGateway(local_settings, cfg, external)
        try:
            email, password = f"integration+{uuid4()}@example.test", secrets.token_urlsafe(32)
            response = await external.post(
                local_settings.supabase_url + "/auth/v1/admin/users",
                headers=headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            assert response.status_code in (200, 201)
            user_id = UUID(response.json()["id"])
            response = await external.post(
                local_settings.supabase_url + "/auth/v1/token?grant_type=password",
                headers={"apikey": local_settings.supabase_publishable_key},
                json={"email": email, "password": password},
            )
            assert response.status_code == 200
            token = response.json()["access_token"]
            app = create_app(local_settings, cfg)
            app.state.engine, app.state.storage = db_engine, gateway
            app.state.verifier = JwtVerifier(local_settings, cfg, external)
            app.state.auth_admin = AuthAdmin(local_settings, external)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": "Bearer " + token},
            ) as api:
                assert (await api.get("/v1/me")).status_code == 200
                case_id, evidence_id = uuid4(), uuid4()
                response = await api.post(
                    "/v1/cases",
                    json={
                        "id": str(case_id),
                        "title": "Synthetic case",
                        "summary": "Synthetic summary",
                        "status": "active",
                    },
                )
                assert response.status_code == 200
                payload = b"synthetic-evidence-bytes"
                response = await api.post(
                    "/v1/evidence/uploads",
                    json={
                        "id": str(evidence_id),
                        "caseId": str(case_id),
                        "filename": "synthetic.bin",
                        "byteSize": len(payload),
                    },
                )
                assert response.status_code == 200
                upload = UploadInfo.model_validate(response.json()["upload"])
                keys.append(upload.object_name)
                created = await start_tus(external, local_settings, upload, len(payload))
                assert created.status_code == 201
                await append_tus(
                    external,
                    local_settings,
                    upload,
                    upload_location(local_settings, created),
                    payload,
                    0,
                )
                assert (await api.post(f"/v1/evidence/{evidence_id}/complete")).status_code == 200
                # A pending capability is already issued when account deletion begins.
                response = await api.post(
                    "/v1/evidence/uploads",
                    json={"id": str(uuid4()), "filename": "pending.bin", "byteSize": len(payload)},
                )
                pending = UploadInfo.model_validate(response.json()["upload"])
                keys.append(pending.object_name)
                conversation_id = uuid4()
                assert (
                    await api.post("/v1/conversations", json={"id": str(conversation_id)})
                ).status_code == 200
                async with db_engine.begin() as conn:
                    await conn.execute(
                        text("INSERT INTO agent_store.agent_sessions(session_id) VALUES(:id)"),
                        {"id": str(conversation_id)},
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO agent_store.agent_messages(session_id,message_data) VALUES(:id,'{}')"
                        ),
                        {"id": str(conversation_id)},
                    )
                response = await api.request("DELETE", "/v1/me", json={"confirm": "DELETE"})
                assert response.status_code == 204, response.text
                assert await gateway.object_info(upload.object_name) is None
                async with admin_db.connect() as conn:
                    assert (
                        await conn.scalar(
                            text("SELECT count(*) FROM auth.users WHERE id=:id"), {"id": user_id}
                        )
                        == 0
                    )
                    assert (
                        await conn.scalar(
                            text("SELECT count(*) FROM app.evidence_items WHERE owner_id=:id"),
                            {"id": user_id},
                        )
                        == 0
                    )
                    assert (
                        await conn.scalar(
                            text(
                                "SELECT count(*) FROM agent_store.agent_sessions WHERE session_id=:id"
                            ),
                            {"id": str(conversation_id)},
                        )
                        == 0
                    )
                assert (
                    await api.request("DELETE", "/v1/me", json={"confirm": "DELETE"})
                ).status_code == 401
                response = await api.post(
                    f"/v1/shares/{uuid4()}/submit",
                    json={"confirmed": True, "confirmationVersion": "v1", "previewHash": "stale"},
                )
                assert response.status_code == 401
                # Storage capabilities survive Auth deletion until their two-hour TTL.
                # This synthetic object demonstrates the explicit operational limitation;
                # the finally block removes it, so the test leaves no orphan behind.
                created = await start_tus(external, local_settings, pending, len(payload))
                assert created.status_code == 201
                await append_tus(
                    external,
                    local_settings,
                    pending,
                    upload_location(local_settings, created),
                    payload,
                    0,
                )
                assert await gateway.object_info(pending.object_name) is not None
        finally:
            await gateway.delete(keys)
            if user_id:
                async with admin_db.begin() as conn:
                    conversation_ids = list(
                        (
                            await conn.execute(
                                text("SELECT id::text FROM app.conversations WHERE owner_id=:id"),
                                {"id": user_id},
                            )
                        ).scalars()
                    )
                    if conversation_ids:
                        await conn.execute(
                            text(
                                "DELETE FROM agent_store.agent_sessions WHERE session_id=ANY(:ids)"
                            ),
                            {"ids": conversation_ids},
                        )
                    await conn.execute(
                        text("DELETE FROM app.cases WHERE owner_id=:id"), {"id": user_id}
                    )
                response = await external.delete(
                    local_settings.supabase_url + f"/auth/v1/admin/users/{user_id}", headers=headers
                )
                assert response.status_code in (200, 204, 404)
            await admin_db.dispose()
