"""Single deployment: API, agent runtime and narrow recovery jobs."""

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.base import FrozenDTO
from moodprint_shared.contracts.errors import ErrorEnvelope
from moodprint_shared.env import EnvSettings, get_settings
from moodprint_shared.logging import configure_logging
from sqlalchemy import text

from app.api.v1.conversations import router as conversation_router
from app.api.v1.me import router as me_router
from app.api.v1.memories import router as memory_router
from app.core.auth import JwtVerifier
from app.core.db import create_engine
from app.core.errors import envelope, register_handlers
from app.core.request_id import RequestIdMiddleware
from app.infrastructure.auth_admin import AuthAdmin
from app.infrastructure.storage_gateway import StorageGateway
from app.jobs.reconcile import reconcile_loop


class HealthReply(FrozenDTO):
    status: Literal["ok"] = "ok"


class ReadyReply(FrozenDTO):
    status: Literal["ready"] = "ready"


def create_app(settings: EnvSettings | None = None, cfg: AppConfig | None = None) -> FastAPI:
    settings = settings or get_settings()
    cfg = cfg or AppConfig()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(production=settings.app_env == "production", level=cfg.logging.level)
        engine = create_engine(settings, cfg)
        async with httpx.AsyncClient(timeout=15) as http:
            app.state.engine, app.state.http = engine, http
            app.state.verifier = JwtVerifier(settings, cfg, http)
            app.state.auth_admin = AuthAdmin(settings, http)
            app.state.storage = StorageGateway(settings, cfg, http)
            from moodprint_agent.runtime import CompanionRuntime
            from openai import AsyncOpenAI

            model_client = (
                AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
                if settings.openai_api_key
                else None
            )
            app.state.runtime = CompanionRuntime(cfg, openai_client=model_client)
            app.state.run_tasks = set()
            reconciler = asyncio.create_task(
                reconcile_loop(engine, cfg.api.reconcile_interval_s, cfg.api.stale_run_after_s)
            )
            try:
                yield
            finally:
                reconciler.cancel()
                with suppress(asyncio.CancelledError):
                    await reconciler
                for task in list(app.state.run_tasks):
                    task.cancel()
                await asyncio.gather(*app.state.run_tasks, return_exceptions=True)
                if model_client:
                    await model_client.close()
                await engine.dispose()

    app = FastAPI(
        title="MoodPrint API",
        version="1.0.0",
        lifespan=lifespan,
        responses={
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 409, 413, 422, 429, 500, 502, 503)
        },
    )
    app.state.settings, app.state.cfg = settings, cfg
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_handlers(app)

    @app.get("/health", response_model=HealthReply)
    async def health():
        return {"status": "ok"}

    @app.get("/ready", response_model=ReadyReply)
    async def ready(request: Request):
        failed = []
        try:
            async with app.state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            failed.append("database")
        try:
            await app.state.verifier.refresh()
        except Exception:
            failed.append("jwks")
        if failed:
            return envelope(
                request, "not_ready", "Dịch vụ chưa sẵn sàng.", 503, {"components": failed}
            )
        return {"status": "ready"}

    app.include_router(me_router)
    app.include_router(memory_router)
    app.include_router(conversation_router)
    return app
