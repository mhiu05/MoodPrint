import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text, update

from app.ai.models import AiTurn
from app.ai.persistence import recover_turns
from app.ai.runtime import AiRuntime
from app.ai.schemas import AIEvent, AiOutput
from app.contracts import ApiError
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import DomainError, install_errors
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import AiRun


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    database = Database(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # No migrations at startup. Restart marks interrupted metadata without replaying model calls.
        if database.sessions:
            async with database.sessions.begin() as db:
                if config.ai_accounting_enabled:
                    from app.ai.accounting import recover_expired

                    await recover_expired(db)
                else:
                    await db.execute(
                        update(AiRun)
                        .where(AiRun.status == "running", ~AiRun.id.in_(select(AiTurn.run_id)))
                        .values(status="interrupted", version=AiRun.version + 1)
                    )
                await recover_turns(db)

        async def sweep_context():
            next_retention = 0.0
            while True:
                app.state.ai.sweep()
                app.state.exports = {
                    key: value
                    for key, value in app.state.exports.items()
                    if value["expires"] > time.monotonic()
                }
                if database.sessions:
                    from app.jobs.retention import purge_expired
                    from app.modules.users.lifecycle import process_deletions

                    try:
                        await process_deletions(app)
                        if time.monotonic() >= next_retention:
                            await purge_expired(app)
                            if config.ai_accounting_enabled:
                                from app.ai.accounting import recover_expired

                                async with database.sessions.begin() as db:
                                    await recover_expired(db)
                            next_retention = time.monotonic() + 60
                    except Exception as error:
                        # SQLSTATE is a content-free class code; never log the message.
                        logging.getLogger("moodprint").error(
                            "deletion_worker_retry error_type=%s sqlstate=%s",
                            type(error).__name__,
                            getattr(getattr(error, "orig", None), "sqlstate", None),
                        )
                await asyncio.sleep(1)

        async def embedding_worker():
            from app.ai.embeddings import process_embedding_jobs

            while True:
                if database.sessions:
                    try:
                        await process_embedding_jobs(database, config)
                    except Exception as error:
                        logging.getLogger("moodprint").error("embedding_worker_retry error_type=%s", type(error).__name__)
                await asyncio.sleep(1)

        sweeper = asyncio.create_task(sweep_context())
        indexer = asyncio.create_task(embedding_worker())
        try:
            yield
        finally:
            sweeper.cancel()
            indexer.cancel()
            await asyncio.gather(sweeper, indexer, return_exceptions=True)
            await app.state.ai.close()
            if database.engine:
                await database.engine.dispose()

    app = FastAPI(
        title="MoodPrint API",
        version="1.0.0",
        lifespan=lifespan,
        # The schema is generated offline (scripts/export_openapi.py); do not serve it publicly.
        docs_url=None if config.app_env == "production" else "/docs",
        redoc_url=None if config.app_env == "production" else "/redoc",
        openapi_url=None if config.app_env == "production" else "/openapi.json",
        responses={
            status: {"model": ApiError} for status in (401, 403, 404, 409, 410, 422, 429, 500, 503)
        },
    )
    app.state.settings, app.state.database = config, database
    app.state.ai = AiRuntime(config, database)
    app.state.exports = {}
    from app.modules.voice.service import OpenAITranscriber

    app.state.transcriber = (
        OpenAITranscriber(config)
        if config.stt_enabled and config.stt_model and config.openai_api_key.get_secret_value()
        else None
    )
    install_errors(app)

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request.state.request_id = str(uuid4())
        content_length = request.headers.get("Content-Length", "0")
        limit = 3_000_000 if request.url.path == "/api/v1/voice/transcriptions" else 65536
        if not content_length.isdigit() or int(content_length) > limit:
            return JSONResponse(
                {
                    "error": {
                        "code": "BODY_TOO_LARGE",
                        "message": "Nội dung yêu cầu quá lớn.",
                        "retryable": False,
                        "requestId": request.state.request_id,
                    }
                },
                status_code=413,
            )
        try:
            response = await call_next(request)
        except Exception as error:
            logging.getLogger("moodprint").error(
                "request_failed request_id=%s error_type=%s",
                request.state.request_id,
                type(error).__name__,
            )
            response = JSONResponse(
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Chưa hoàn tất yêu cầu. Vui lòng thử lại.",
                        "retryable": True,
                        "requestId": request.state.request_id,
                    }
                },
                status_code=500,
            )
        path = request.url.path
        hashed = path.startswith("/assets/") and response.status_code == 200
        response.headers.update(
            {
                "Cache-Control": "public, max-age=31536000, immutable" if hashed else "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Request-ID": request.state.request_id,
                "Referrer-Policy": "no-referrer",
            }
        )
        if not path.startswith("/api/"):
            response.headers.update(
                {
                    "Content-Security-Policy": CSP,
                    "X-Frame-Options": "DENY",
                    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
                }
            )
        if config.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/api/v1/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/api/v1/health/ready")
    async def ready():
        try:
            async with database.require()() as db:
                await db.execute(text("select 1"))
                revision = await db.scalar(
                    text("select version_num from moodprint.alembic_version")
                )
                if revision != "0010_account_deletion":
                    raise RuntimeError("Migration required")
                helper = await db.scalar(
                    text(
                        "select to_regprocedure('moodprint.is_provider_session_active(uuid,uuid)') is not null"
                    )
                )
                if not helper:
                    raise RuntimeError("Reviewed Auth security bootstrap required")
        except Exception as exc:
            raise DomainError(503, "NOT_READY", "Dịch vụ dữ liệu chưa sẵn sàng.", True) from exc
        return {"status": "ready"}

    from app.ai.chat_routes import router as ai
    from app.ai.memory import router as memory
    from app.modules.auth.routes import router as auth
    from app.modules.consent.routes import router as consent
    from app.modules.moderation.routes import router as moderation
    from app.modules.mood.routes import router as mood
    from app.modules.profiles.routes import router as profiles
    from app.modules.social.notifications import router as notifications
    from app.modules.social.routes import router as social
    from app.modules.users.routes import router as users
    from app.modules.voice.routes import router as voice

    for router in (
        auth,
        consent,
        profiles,
        mood,
        ai,
        memory,
        social,
        moderation,
        notifications,
        voice,
        users,
    ):
        app.include_router(router, prefix="/api/v1")

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["components"]["schemas"]["AIEvent"] = AIEvent.model_json_schema(by_alias=True)
        output = AiOutput.model_json_schema(
            by_alias=True, ref_template="#/components/schemas/{model}"
        )
        schema["components"]["schemas"].update(output.pop("$defs", {}))
        schema["components"]["schemas"]["AiOutput"] = output
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    if config.static_dir:
        install_static(app, Path(config.static_dir))
    app.add_middleware(BodyLimitMiddleware)
    return app


CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "connect-src 'self'; media-src 'self' blob:; worker-src 'self'; font-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


def install_static(app: FastAPI, root: Path) -> None:
    """Serve the built SPA from the API origin (same-origin cookies and CSRF checks)."""
    root = root.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError("STATIC_DIR must contain the built index.html")
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")
    top_level = {item.name for item in root.iterdir() if item.is_file()}

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy.")
        if path in top_level:
            return FileResponse(root / path)
        # Client-side routes (including /auth/callback) all load the same shell.
        return FileResponse(index)


app = create_app()
