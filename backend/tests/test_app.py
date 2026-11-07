import httpx
import pytest
from app.main import create_app
from moodprint_shared.env import EnvSettings


@pytest.fixture
def settings():
    return EnvSettings(
        app_env="test",
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="test-public",
        supabase_secret_key="test-secret",
        database_url="postgresql+asyncpg://moodprint_api:local@127.0.0.1:54322/postgres",
        cors_allowed_origins=["http://127.0.0.1:5173"],
    )


async def test_health_needs_no_dependencies(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_503_names_component_only(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["details"]["components"] == ["database", "jwks"]
    assert "test-secret" not in response.text


async def test_request_id_echoed(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "test-request-42"})
    assert response.headers["X-Request-ID"] == "test-request-42"


async def test_invalid_request_id_replaced(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "bad request"})
    assert response.headers["X-Request-ID"] != "bad request"


async def test_error_envelope_shape(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/v1/me")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "requestId", "details"}


async def test_unknown_route_has_safe_error_envelope(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/v1/not-a-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_unhandled_error_hides_details(settings):
    app = create_app(settings)

    @app.get("/test-error")
    async def broken():
        raise RuntimeError("sensitive-test-content")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/test-error")
    assert response.status_code == 500
    assert "sensitive-test-content" not in response.text
    assert response.headers.get("X-Request-ID")


async def test_cors_rejects_unknown_origin(settings):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.options(
            "/v1/me",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_startup_shutdown_closes_engine(settings, monkeypatch):
    from unittest.mock import AsyncMock

    from app.core.db import create_engine

    engine = create_engine(
        settings, __import__("moodprint_shared.config", fromlist=["AppConfig"]).AppConfig()
    )
    original_dispose = engine.dispose
    dispose = AsyncMock(side_effect=original_dispose)

    class TrackedEngine:
        def begin(self):
            return engine.begin()

        async def dispose(self):
            await dispose()

    monkeypatch.setattr("app.main.create_engine", lambda settings, cfg: TrackedEngine())
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        http = app.state.http
        assert not http.is_closed
    assert http.is_closed
    dispose.assert_awaited_once()
