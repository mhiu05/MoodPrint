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
from app.ai.schemas import AIEvent, AIFinalV2, AiOutput
from app.contracts import ApiError
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import DomainError, install_errors, render_unexpected
from app.core.revisions import READY_REVISIONS
from app.infrastructure.database.budget import has_deployment_headroom
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import AiRun
from app.modules.guests.output import GuestOutputMiddleware


def warn_unenforced_budget(config) -> None:
    if config.ai_daily_budget_usd > 0 and not config.ai_accounting_enabled:
        logging.getLogger("moodprint").warning(
            "ai_budget_unenforced reason=accounting_disabled"
        )


def warn_pool_budget(config) -> None:
    if not has_deployment_headroom(config.database_pool_size, config.database_pool_overflow):
        logging.getLogger("moodprint").warning(
            "database_pool_exceeds_headroom size=%s overflow=%s",
            config.database_pool_size,
            config.database_pool_overflow,
        )


def pool_counts(database) -> tuple[int | str, int | str]:
    method = getattr(database, "occupancy", None)
    if not callable(method):
        return "-", "-"
    try:
        checked, overflow = method()
    except Exception:
        return "-", "-"
    if isinstance(checked, int) and isinstance(overflow, int):
        return checked, overflow
    return "-", "-"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    warn_unenforced_budget(config)
    warn_pool_budget(config)
    shell_policy = content_security_policy(bool(config.guest_captcha_site_key),
        storage_origin=config.supabase_url if config.journal_storage_key.get_secret_value() else "")
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

        sweep_clock = {"retention": 0.0, "sample": 0.0}
        guest_clock = {"metrics": 0.0, "retention": 0.0, "first": True}

        async def sweep_pass() -> None:
            from app.modules.social.notifications import STREAM_SLOTS

            app.state.ai.sweep()
            if time.monotonic() >= sweep_clock["sample"]:
                metrics = logging.getLogger("moodprint")
                metrics.info("metric=sse_streams_open value=%d", STREAM_SLOTS.open())
                metrics.info("metric=http_requests value=%d", app.state.http_requests)
                checked_out, overflow = pool_counts(database)
                if isinstance(checked_out, int):
                    metrics.info("metric=db_pool_checked_out value=%d", checked_out)
                    metrics.info("metric=db_pool_overflow value=%d", overflow if isinstance(overflow, int) else 0)
                app.state.http_requests = 0
                sweep_clock["sample"] = time.monotonic() + 60
            app.state.exports = {
                key: value
                for key, value in app.state.exports.items()
                if value["expires"] > time.monotonic()
            }
            if database.sessions:
                from app.jobs.retention import purge_expired
                from app.modules.users.lifecycle import process_deletions

                try:
                    from app.modules.activities.jobs import advance_due

                    await process_deletions(app)
                    await advance_due(app)
                    if time.monotonic() >= sweep_clock["retention"]:
                        await purge_expired(app)
                        if config.ai_accounting_enabled:
                            from app.ai.accounting import recover_expired

                            async with database.sessions.begin() as db:
                                await recover_expired(db)
                        sweep_clock["retention"] = time.monotonic() + 60
                except Exception as error:
                    # SQLSTATE is a content-free class code; never log the message.
                    logging.getLogger("moodprint").error(
                        "deletion_worker_retry error_type=%s sqlstate=%s",
                        type(error).__name__,
                        getattr(getattr(error, "orig", None), "sqlstate", None),
                    )

        async def embedding_pass() -> None:
            if not database.sessions:
                return
            from app.ai.embeddings import process_embedding_jobs

            try:
                await process_embedding_jobs(database, config)
            except Exception as error:
                logging.getLogger("moodprint").error(
                    "embedding_worker_retry error_type=%s", type(error).__name__
                )

        async def guest_pass() -> None:
            """Guest expiry cleanup and orphan reconciliation: always on, isolated per work class."""
            if not database.sessions:
                return
            from app.modules.guests.jobs import (
                ensure_cleanup_jobs,
                guest_metrics,
                process_guest_cleanup,
                reconcile_guest_provisioning,
                retention_tick,
                settle_stale_liability,
            )

            for work in (
                ensure_cleanup_jobs if guest_clock["first"] else None,
                process_guest_cleanup,
                reconcile_guest_provisioning,
                settle_stale_liability,
                retention_tick if time.monotonic() >= guest_clock["retention"] else None,
            ):
                if work is retention_tick:
                    guest_clock["retention"] = time.monotonic() + 60
                if work is None:
                    continue
                try:
                    await work(app)
                    if work is ensure_cleanup_jobs:
                        guest_clock["first"] = False
                except Exception as error:
                    logging.getLogger("moodprint").error(
                        "guest_worker_retry task=%s error_type=%s sqlstate=%s",
                        work.__name__,
                        type(error).__name__,
                        getattr(getattr(error, "orig", None), "sqlstate", None),
                    )
            if time.monotonic() >= guest_clock["metrics"]:
                try:
                    for name, value in (await guest_metrics(app)).items():
                        logging.getLogger("moodprint").info("metric=%s value=%s", name, value)
                except Exception as error:
                    logging.getLogger("moodprint").error(
                        "guest_metrics_failed error_type=%s", type(error).__name__
                    )
                guest_clock["metrics"] = time.monotonic() + 30

        async def journal_pass() -> None:
            from app.modules.journal.storage import process_storage_cleanup

            try:
                await process_storage_cleanup(app)
            except Exception as error:
                logging.getLogger("moodprint").error(
                    "journal_cleanup_failed error_type=%s", type(error).__name__
                )

        # Finish one pass before accepting traffic. Otherwise its pool checkouts
        # share the event loop with the first requests.
        await sweep_pass()
        await embedding_pass()
        await guest_pass()
        await journal_pass()

        async def sweep_context():
            # The opening pass already ran. Wait before repeating it so the first
            # requests are not checked out against that work.
            await asyncio.sleep(3)
            while True:
                await sweep_pass()
                await asyncio.sleep(1)

        async def embedding_worker():
            await asyncio.sleep(3)
            while True:
                await embedding_pass()
                await asyncio.sleep(1)

        async def guest_worker():
            await asyncio.sleep(3)
            while True:
                await guest_pass()
                await asyncio.sleep(1)

        async def journal_worker():
            while True:
                await asyncio.sleep(60)
                await journal_pass()

        sweeper = asyncio.create_task(sweep_context())
        indexer = asyncio.create_task(embedding_worker())
        guests = asyncio.create_task(guest_worker())
        journal_cleanup = asyncio.create_task(journal_worker())
        try:
            yield
        finally:
            sweeper.cancel()
            indexer.cancel()
            guests.cancel()
            journal_cleanup.cancel()
            await asyncio.gather(sweeper, indexer, guests, journal_cleanup, return_exceptions=True)
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
    from app.modules.journal.storage import SupabaseJournalStorage
    storage = SupabaseJournalStorage(config)
    app.state.journal_storage = storage if storage.available else None
    app.state.http_requests = 0
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
        started = time.perf_counter()
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
            response = render_unexpected(request, error)
        path = request.url.path
        if path.startswith("/api/"):
            app.state.http_requests += 1
            route = request.scope.get("route")
            template = getattr(route, "path", None)
            if not isinstance(template, str) or len(template) > 120 or not template.startswith("/"):
                template = "unmatched"
            checked_out, overflow = pool_counts(database)
            logging.getLogger("moodprint").info(
                "request_completed request_id=%s route=%s status=%s duration_ms=%.1f category=%s error_type=%s sqlstate=%s release=%s pool_checked_out=%s pool_overflow=%s",
                request.state.request_id,
                template,
                response.status_code,
                (time.perf_counter() - started) * 1000,
                getattr(request.state, "error_category", "-"),
                getattr(request.state, "error_type", "-"),
                getattr(request.state, "sqlstate", "-"),
                config.release_sha,
                checked_out if checked_out is not None else "-",
                overflow if overflow is not None else "-",
            )
            if response.status_code >= 500:
                logging.getLogger("moodprint").warning("metric=http_5xx")
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
                    "Content-Security-Policy": shell_policy,
                    "X-Frame-Options": "DENY",
                    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
                }
            )
            if path == "/auth/callback":
                # The email-link landing carries one-time fragments: never indexed, never cached.
                response.headers["X-Robots-Tag"] = "noindex, nofollow"
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
                if revision not in READY_REVISIONS:
                    raise RuntimeError("Migration required")
                helper = await db.scalar(
                    text(
                        "select to_regprocedure('moodprint.is_provider_session_active(uuid,uuid)') is not null"
                    )
                )
                if not helper:
                    raise RuntimeError("Reviewed Auth security bootstrap required")
        except Exception as exc:
            logging.getLogger("moodprint").warning("metric=readiness_failed")
            raise DomainError(503, "NOT_READY", "Dịch vụ dữ liệu chưa sẵn sàng.", True) from exc
        return {"status": "ready"}

    from app.ai.chat_routes import router as ai
    from app.ai.collaboration.routes import router as sharing
    from app.ai.groups.routes import router as groups
    from app.ai.memory import router as memory
    from app.ai.proactive.routes import router as proactive
    from app.modules.activities.routes import router as activities
    from app.modules.auth.routes import router as auth
    from app.modules.consent.routes import router as consent
    from app.modules.feedback.admin_routes import router as feedback_admin
    from app.modules.feedback.routes import router as feedback
    from app.modules.guests.routes import router as guests
    from app.modules.journal.media_routes import router as journal_media
    from app.modules.journal.routes import router as journal
    from app.modules.moderation.admin_routes import router as moderation_admin
    from app.modules.moderation.routes import router as moderation
    from app.modules.mood.routes import router as mood
    from app.modules.profiles.routes import router as profiles
    from app.modules.social.notifications import router as notifications
    from app.modules.social.routes import router as social
    from app.modules.social.summary import router as social_summary
    from app.modules.users.routes import router as users
    from app.modules.voice.routes import router as voice

    for router in (
        auth,
        guests,
        feedback,
        feedback_admin,
        consent,
        profiles,
        mood,
        journal,
        journal_media,
        ai,
        proactive,
        sharing,
        groups,
        memory,
        social,
        social_summary,
        activities,
        moderation,
        moderation_admin,
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
        final = AIFinalV2.model_json_schema(by_alias=True, ref_template="#/components/schemas/{model}")
        schema["components"]["schemas"].update(final.pop("$defs", {}))
        schema["components"]["schemas"]["AIFinalV2"] = final
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    if config.static_dir:
        install_static(app, Path(config.static_dir))
    app.add_middleware(BodyLimitMiddleware)
    # Outermost: wraps the send every other middleware ultimately calls.
    app.add_middleware(GuestOutputMiddleware)
    return app


CAPTCHA_ORIGIN = "https://challenges.cloudflare.com"


def content_security_policy(captcha: bool = False, *, storage_origin: str = "") -> str:
    """Strict same-origin policy; the CAPTCHA origin is added only while a site key is configured.

    With the guest entry disabled (no key) nothing third-party can load. When enabled the challenge
    needs its script, its frame and its verification request and nothing else.
    """
    extra = f" {CAPTCHA_ORIGIN}" if captcha else ""
    frame = f"frame-src {CAPTCHA_ORIGIN}; " if captcha else ""
    from app.modules.journal.storage import storage_origins
    storage = "".join(f" {origin}" for origin in storage_origins(storage_origin))
    return (
        f"default-src 'self'; script-src 'self'{extra}; style-src 'self'; "
        f"img-src 'self' data: blob:{storage}; connect-src 'self'{extra}{storage}; media-src 'self' blob:{storage}; "
        f"{frame}worker-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )


CSP = content_security_policy()


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
