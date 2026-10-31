import httpx
import pytest


@pytest.mark.asyncio
async def test_live_works_without_configuration_but_ready_and_auth_fail_closed():
    from app.main import create_app

    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/health/live")).status_code == 200
        assert (await client.get("/api/v1/health/ready")).status_code == 503
        response = await client.get("/api/v1/session")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"
        assert "requestId" in response.json()["error"]


def test_ready_revisions_cover_the_reviewed_migration_window():
    from app.core.revisions import READY_REVISIONS

    # V3 maps ai_conversations.kind/active_agent and ai_messages.mentions, so only 0024 is ready.
    assert READY_REVISIONS == (
        "0024_three_agent_groups",
    )


@pytest.mark.parametrize(
    ("revision", "expected_status"),
    [
        ("0010_account_deletion", 503),
        ("0011_social_stabilization", 503),
        ("0012_matching_v2", 503),
        ("0013_shared_activities", 503),
        ("0014_moderation", 503),
        ("0015_context_privacy", 503),
        ("0016_guest_foundation", 503),
        ("0017_guest_security", 503),
        ("0018_app_feedback", 503),
        ("0019_journal", 503),
        ("0020_private_profile_retirement", 503),
        ("0021_multi_message", 503),
        ("0022_proactive_messages", 503),
        ("0023_collaboration", 503),
        ("0024_three_agent_groups", 200),
        ("0017_unreviewed", 503),
    ],
)
async def test_ready_supports_expand_migration_window_and_rejects_unknown(
    monkeypatch, revision, expected_status
):
    from app import main

    class FakeSession:
        def __init__(self):
            self.scalar_results = iter((revision, True))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, _):
            return None

        async def scalar(self, _):
            return next(self.scalar_results)

    class FakeDatabase:
        def __init__(self, _):
            self.engine = None
            self.sessions = None

        def require(self):
            return FakeSession

    monkeypatch.setattr(main, "Database", FakeDatabase)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/ready")
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_bots_are_public_but_do_not_expose_prompts_or_tools():
    from app.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/bots")
        assert response.status_code == 200
        bots = response.json()
        assert {bot["botId"] for bot in bots} == {"may", "guong", "nhip", "rure", "caunoi"}
        assert all("instructions" not in bot and "tools" not in bot for bot in bots)


def test_database_configuration_rejects_sqlite_and_invalid_pool_modes():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///test.db")
    with pytest.raises(ValueError):
        Settings(database_pool_mode="unknown")


def test_destructive_test_setup_rejects_remote_targets_before_any_connection():
    from tests.database_target import require_local_test_database

    for target in (
        "postgresql+psycopg://fixture:fixture@remote.example/moodprint_test",
        "postgresql+psycopg://fixture:fixture@localhost/moodprint",
        "sqlite:///moodprint_test",
    ):
        with pytest.raises(RuntimeError):
            require_local_test_database(target)
    assert (
        require_local_test_database("postgresql+psycopg://localhost/moodprint_test").database
        == "moodprint_test"
    )


def test_openapi_contains_safe_typed_contracts_and_unified_errors():
    from app.main import create_app

    schema = create_app().openapi()
    assert "SessionView" in schema["components"]["schemas"]
    assert "ApiError" in schema["components"]["schemas"]
    assert "password" not in schema["components"]["schemas"]["SessionView"]["properties"]


async def test_unexpected_error_does_not_escape_the_boundary_or_log_private_input(caplog):
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(_env_file=None))

    @app.get("/test-private-error")
    async def private_error():
        raise RuntimeError("PRIVATE-ERROR-CANARY")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/test-private-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "PRIVATE-ERROR-CANARY" not in response.text + caplog.text


async def test_chunked_body_without_content_length_cannot_bypass_request_limit():
    from app.core.config import Settings
    from app.main import create_app

    async def chunks():
        yield b"a" * 40000
        yield b"b" * 40000

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(Settings(_env_file=None))),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "BODY_TOO_LARGE"


async def test_spa_is_served_same_origin_without_shadowing_the_api(tmp_path):
    import httpx

    from app.core.config import Settings
    from app.main import create_app

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "me2we.svg").write_text("<svg/>", encoding="utf-8")
    app = create_app(Settings(_env_file=None, static_dir=str(tmp_path)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        shell = await c.get("/auth/callback")
        assert shell.status_code == 200 and "id=root" in shell.text
        assert "frame-ancestors 'none'" in shell.headers["Content-Security-Policy"]
        assert "script-src 'self'" in shell.headers["Content-Security-Policy"]
        assert shell.headers["Cache-Control"] == "no-store"
        asset = await c.get("/assets/index-abc.js")
        assert asset.status_code == 200 and "immutable" in asset.headers["Cache-Control"]
        assert (await c.get("/me2we.svg")).text == "<svg/>"
        api = await c.get("/api/v1/does-not-exist")
        assert api.status_code == 404 and "id=root" not in api.text
        assert "Content-Security-Policy" not in api.headers
        escape = await c.get("/..%2F..%2Fpyproject.toml")
        assert "id=root" in escape.text
