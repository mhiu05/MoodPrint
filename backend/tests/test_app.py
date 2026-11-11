import httpx
import pytest
from app.main import create_app
from safevoice_shared.env import EnvSettings


@pytest.fixture
def settings():
    return EnvSettings(
        app_env="test",
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="test-public",
        supabase_secret_key="test-secret",
        database_url="postgresql+asyncpg://safevoice_api:local@127.0.0.1:54322/postgres",
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
        settings, __import__("safevoice_shared.config", fromlist=["AppConfig"]).AppConfig()
    )
    original_dispose = engine.dispose
    dispose = AsyncMock(side_effect=original_dispose)

    class TrackedEngine:
        def begin(self):
            return engine.begin()

        async def dispose(self):
            await dispose()

    monkeypatch.setattr("app.main.create_engine", lambda settings, cfg: TrackedEngine())
    # This test is about resource lifetimes, not retrieval: choose the fixture on purpose (the product
    # default is the real retriever and needs a Voyage key).
    from dataclasses import replace

    from safevoice_shared.config import AppConfig

    base = AppConfig()
    app = create_app(
        settings, replace(base, knowledge=replace(base.knowledge, retriever="fixture"))
    )
    async with app.router.lifespan_context(app):
        http = app.state.http
        assert not http.is_closed
    assert http.is_closed
    dispose.assert_awaited_once()


async def test_lifespan_injects_knowledge_before_building_runtime(settings, monkeypatch):
    from safevoice_shared.config import AppConfig
    from safevoice_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope
    from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

    app = create_app(settings)
    retriever = FixtureKnowledgeRetriever()
    runtime = object()

    def knowledge_factory(engine, actual_settings, cfg):
        assert engine is app.state.engine
        assert actual_settings is settings
        assert isinstance(cfg, AppConfig)
        return retriever

    def runtime_factory(cfg, model_client):
        assert app.state.knowledge is retriever
        assert model_client is None
        return runtime

    monkeypatch.setattr("app.main.build_knowledge_retriever", knowledge_factory, raising=False)
    monkeypatch.setattr("app.main.build_runtime", runtime_factory, raising=False)
    async with app.router.lifespan_context(app):
        assert app.state.runtime is runtime
        result = await app.state.knowledge.search(
            KnowledgeQuery(text="friends"),
            scope=RetrievalScope(request_id="startup-test"),
            timeout_s=1,
        )
        assert result.corpus_version == "synthetic-fixture-v1"


async def test_startup_factory_failure_closes_acquired_resources(settings, monkeypatch):
    from dataclasses import replace
    from unittest.mock import AsyncMock

    from safevoice_shared.config import AppConfig

    dispose = AsyncMock()
    monkeypatch.setattr(
        "app.main.create_engine", lambda settings, cfg: type("Engine", (), {"dispose": dispose})()
    )
    cfg = AppConfig()
    cfg = replace(cfg, knowledge=replace(cfg.knowledge, retriever="unavailable"))
    app = create_app(settings, cfg)
    with pytest.raises(ValueError, match="Unknown knowledge retriever"):
        async with app.router.lifespan_context(app):
            pytest.fail("invalid retriever must fail startup")
    assert app.state.http.is_closed
    dispose.assert_awaited_once()


@pytest.mark.parametrize(
    "module,prefix", [("analyses", "/v1/analyses"), ("roleplay", "/v1/roleplay")]
)
async def test_phase3_can_add_router_endpoint_without_changing_app_factory(
    settings, monkeypatch, module, prefix
):
    from importlib import import_module

    router = import_module(f"app.api.v1.{module}").router
    monkeypatch.setattr(router, "routes", [])

    async def probe():
        return {"module": module}

    router.add_api_route("/seam-probe", probe, methods=["GET"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get(prefix + "/seam-probe")
    assert response.status_code == 200
    assert response.json() == {"module": module}
