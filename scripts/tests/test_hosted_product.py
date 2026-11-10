"""Offline safety checks: this suite never contacts a hosted service."""

import json
from uuid import uuid4

import httpx
import pytest

from scripts import hosted_product as hosted


def values():
    return {
        "SUPABASE_URL": "https://xhlshihobyxrgfqrdafh.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "synthetic-public",
        "SUPABASE_SECRET_KEY": "synthetic-secret",
        "DATABASE_URL": "postgresql+asyncpg://moodprint_api.xhlshihobyxrgfqrdafh:synthetic@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require",
        "OPENAI_API_KEY": "must-not-use",
        "VOYAGE_API_KEY": "synthetic-voyage",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SUPABASE_URL", "http://127.0.0.1:54321"),
        ("SUPABASE_URL", "https://old-project.supabase.co"),
        ("SUPABASE_URL", "https://xhlshihobyxrgfqrdafh.supabase.co@evil.invalid"),
        ("SUPABASE_URL", "https://xhlshihobyxrgfqrdafh.supabase.co?secret=redacted"),
        ("DATABASE_URL", "postgresql+asyncpg://moodprint_api:synthetic@127.0.0.1:54322/postgres"),
        (
            "DATABASE_URL",
            "postgresql+asyncpg://moodprint_api.old-project:synthetic@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        ),
        (
            "DATABASE_URL",
            "postgresql+asyncpg://postgres.xhlshihobyxrgfqrdafh:synthetic@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        ),
        (
            "DATABASE_URL",
            "postgresql+asyncpg://moodprint_api.xhlshihobyxrgfqrdafh:synthetic@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?host=evil.invalid",
        ),
    ],
)
def test_wrong_project_or_database_override_fails_without_echoing_secrets(field, value):
    supplied = values() | {field: value}
    with pytest.raises(ValueError) as error:
        hosted.validate_target(supplied)
    assert "synthetic" not in str(error.value)
    assert "evil.invalid" not in str(error.value)


def test_child_environment_uses_real_auth_without_inherited_paid_or_local_bootstrap_settings():
    child = hosted.build_environment(
        values(),
        {
            "PATH": "system-path",
            "OPENAI_API_KEY": "forbidden",
            "TEST_ADMIN_DATABASE_URL": "forbidden",
            "E2E_HOOKS": "forbidden",
        },
    )
    assert child["APP_ENV"] == "development"
    assert child["VITE_PUBLIC_SUPABASE_URL"] == "https://xhlshihobyxrgfqrdafh.supabase.co"
    assert child["VITE_PUBLIC_API_BASE_URL"] == "http://127.0.0.1:8010"
    assert child["OPENAI_API_KEY"] == ""
    assert child["OPENAI_AGENTS_DISABLE_TRACING"] == "1"
    assert "TEST_ADMIN_DATABASE_URL" not in child
    assert "E2E_HOOKS" not in child


def manifest(path):
    data = hosted.new_manifest()
    for user in data["users"]:
        user["id"] = str(uuid4())
    hosted.write_manifest(path, data)
    return data


def test_storage_cleanup_refuses_keys_outside_exact_synthetic_user_ids(tmp_path):
    path = tmp_path / "users.json"
    data = manifest(path)
    own = f"users/{data['users'][0]['id']}/originals/{uuid4()}/image.png"
    hosted.record_storage_key(path, own)
    assert hosted.read_manifest(path)["storage_keys"] == [own]
    with pytest.raises(ValueError):
        hosted.record_storage_key(path, f"users/{uuid4()}/originals/{uuid4()}/other.png")
    with pytest.raises(ValueError):
        hosted.record_storage_key(path, own + "/../unknown")
    assert hosted.read_manifest(path)["storage_keys"] == [own]


@pytest.mark.asyncio
async def test_prepare_creates_exactly_two_confirmed_users_and_persists_ids_before_return(tmp_path):
    path = tmp_path / "users.json"
    calls = []

    def auth(request):
        calls.append(request)
        assert request.url.path == "/auth/v1/admin/users"
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["email_confirm"] is True
        assert body["email"].endswith("@example.test")
        return httpx.Response(200, json={"id": str(uuid4())})

    async with httpx.AsyncClient(transport=httpx.MockTransport(auth)) as http:
        await hosted.prepare(values(), path, http)
        await hosted.prepare(values(), path, http)
    assert len(calls) == 2
    data = hosted.read_manifest(path)
    assert len({user["id"] for user in data["users"]}) == 2
    assert all(user["password"] for user in data["users"])


@pytest.mark.asyncio
async def test_http_transport_blocks_paid_and_unapproved_hosts_before_network():
    transport = hosted.ProjectTransport()
    async with httpx.AsyncClient(transport=transport) as http:
        for url in (
            "https://api.openai.com/v1/responses",
            "https://api.voyageai.com/v1/embeddings",
            "http://127.0.0.1:54321/auth/v1/user",
        ):
            with pytest.raises(ValueError, match="audited project"):
                await http.get(url)


@pytest.mark.asyncio
async def test_hosted_lifespan_does_not_enter_production_jobs_or_paid_model(tmp_path, monkeypatch):
    from app import main

    from scripts import hosted_product_app as seam

    path = tmp_path / "users.json"
    manifest(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Production maintenance/model wiring entered")

    class Engine:
        disposed = False

        async def dispose(self):
            self.disposed = True

    engine = Engine()
    monkeypatch.setattr(main, "purge_loop", forbidden)
    monkeypatch.setattr(main, "reconcile_loop", forbidden)
    monkeypatch.setattr(main, "build_runtime", forbidden)
    monkeypatch.setattr(main, "create_engine", forbidden)
    monkeypatch.setattr(seam, "create_engine", lambda *_: engine)
    app = seam.create_app(values(), path)
    async with app.router.lifespan_context(app):
        assert app.state.run_tasks == set()
        # The fake HTTP transport answers without allowing network access.
        client = app.state.runtime.openai_client
        response = await client.responses.create(model="synthetic", input="hello")
        assert response.id == "resp_e2e"
    assert engine.disposed


@pytest.mark.asyncio
async def test_hosted_verifier_rejects_valid_but_unrecorded_user(monkeypatch):
    from app.core.auth import JwtVerifier
    from app.core.errors import ApiError
    from moodprint_shared.contracts.auth import AuthContext

    from scripts.hosted_product_app import SyntheticVerifier

    user_id = uuid4()

    async def verified(*args):
        return AuthContext(user_id=user_id, session_id="synthetic", aal="aal1", claims_json="{}")

    monkeypatch.setattr(JwtVerifier, "verify", verified)
    verifier = SyntheticVerifier(None, None, None, {str(uuid4())})
    with pytest.raises(ApiError) as error:
        await verifier.verify("synthetic-token")
    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exists", "reason"),
    [
        (None, "hosted_knowledge_schema_missing"),
        ("knowledge.corpus_versions", "hosted_paid_retrieval_disabled"),
    ],
)
async def test_retrieval_guard_never_invokes_configured_paid_adapter(exists, reason):
    from moodprint_shared.contracts.errors import KnowledgeUnavailable

    from scripts.hosted_product_app import BlockPaidRetrieval

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def scalar(self, statement):
            assert "pg_catalog.pg_class" in str(statement)
            assert "knowledge" in str(statement)
            return exists

    class Engine:
        def connect(self):
            return Connection()

    class PaidAdapter:
        async def search(self, *_args, **_kwargs):
            raise AssertionError("Paid retrieval must never be invoked")

    guarded = BlockPaidRetrieval(Engine(), PaidAdapter())
    with pytest.raises(KnowledgeUnavailable) as error:
        await guarded.search(None, scope=None, timeout_s=10)
    assert error.value.details["reason"] == reason


@pytest.mark.asyncio
async def test_hosted_seam_blocks_case_route_that_invokes_global_purge(tmp_path):
    from scripts.hosted_product_app import create_app

    path = tmp_path / "users.json"
    manifest(path)
    app = create_app(values(), path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://synthetic-api"
    ) as api:
        response = await api.delete(f"/v1/cases/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "hosted_global_maintenance_blocked"
