"""Explicit hosted synthetic seam; production lifespan is never entered.

Real ES256 Auth, user-scoped SQL and Storage. Scripted model responses and paid
retrieval blocking are deliberate test seams, not evidence of model quality.
"""

import asyncio
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from agents import set_tracing_disabled
from app.core.auth import JwtVerifier
from app.core.db import create_engine
from app.core.errors import ApiError, envelope
from app.infrastructure.auth_admin import AuthAdmin
from app.infrastructure.storage_gateway import StorageGateway
from app.main import create_app as foundation_app
from app.modules.knowledge.factory import build_knowledge_retriever
from moodprint_agent.testing.scripted_scenarios import build_e2e_runtime
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import KnowledgeUnavailable
from moodprint_shared.env import EnvSettings
from sqlalchemy import text

from scripts.hosted_product import (
    MANIFEST,
    ProjectTransport,
    read_manifest,
    record_storage_key,
    require_storage_key,
    validate_target,
)

RELATIONS = (
    "app.profiles",
    "app.cases",
    "app.evidence_items",
    "app.action_plans",
    "app.user_memories",
    "app.agent_proposals",
    "app.analysis_requests",
    "app.roleplay_sessions",
    "app.message_attachments",
    "app.message_assessments",
    "knowledge.corpus_versions",
    "agent_store.agent_sessions",
)


class SyntheticVerifier(JwtVerifier):
    def __init__(self, settings, cfg, http, user_ids: set[str]):
        super().__init__(settings, cfg, http)
        self.user_ids = user_ids

    async def verify(self, token):
        auth = await super().verify(token)
        if str(auth.user_id) not in self.user_ids:
            raise ApiError(
                "forbidden", "Hosted product seam accepts recorded synthetic users only.", 403
            )
        return auth


class SyntheticStorage(StorageGateway):
    def __init__(self, settings, cfg, http, path: Path, user_ids: set[str]):
        super().__init__(settings, cfg, http)
        self.manifest_path, self.user_ids = path, user_ids

    def _object(self, key):
        require_storage_key(key, self.user_ids)
        return super()._object(key)

    async def create_upload_token(self, key):
        record_storage_key(self.manifest_path, key)
        return await super().create_upload_token(key)

    async def delete(self, keys):
        for key in keys:
            require_storage_key(key, self.user_ids)
        return await super().delete(keys)


class BlockPaidRetrieval:
    """Retain the configured real adapter but do not invoke its paid query embedding."""

    def __init__(self, engine, configured):
        self.engine, self.configured = engine, configured

    async def search(self, query, *, scope, timeout_s):
        del query, scope, timeout_s
        async with self.engine.connect() as connection:
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='knowledge' AND c.relname='corpus_versions')"
                )
            )
        reason = "hosted_paid_retrieval_disabled" if exists else "hosted_knowledge_schema_missing"
        raise KnowledgeUnavailable(
            "Hosted retrieval is unavailable; corpus deployment and paid query embeddings require a separate verified gate.",
            details={"reason": reason},
        )


def create_app(
    values: dict[str, str] | None = None, manifest_path: Path = MANIFEST, *, allow_incomplete=False
):
    if values is None:
        if os.environ.get("MOODPRINT_HOSTED_PRODUCT") != "1":
            raise ValueError("Hosted product factory requires the explicit hosted runner")
        values = dict(os.environ)
    validate_target(values)
    data = read_manifest(manifest_path, require_ready=not allow_incomplete)
    user_ids = {user["id"] for user in data["users"] if user["id"] and not user["deleted"]}
    database = values["DATABASE_URL"]
    if "?" not in database:
        database += "?sslmode=require"
    # Supply every paid credential explicitly so BaseSettings cannot read owner dotenv/process fallbacks.
    settings = EnvSettings(
        _env_file=None,
        APP_ENV="development",
        SUPABASE_URL=values["SUPABASE_URL"],
        SUPABASE_PUBLISHABLE_KEY=values["SUPABASE_PUBLISHABLE_KEY"],
        SUPABASE_SECRET_KEY=values["SUPABASE_SECRET_KEY"],
        DATABASE_URL=database,
        CORS_ALLOWED_ORIGINS=["http://127.0.0.1:5183"],
        OPENAI_API_KEY=None,
        VOYAGE_API_KEY=values.get("VOYAGE_API_KEY") or None,
        APIFY_API_TOKEN=None,
        AUTH_TEST_JWT_SECRET=None,
        SUPABASE_DB_URL=None,
    )
    cfg = AppConfig()
    app = foundation_app(settings, cfg)

    @asynccontextmanager
    async def lifespan(application):
        set_tracing_disabled(True)
        engine = create_engine(settings, cfg)
        runtime = None
        async with httpx.AsyncClient(
            transport=ProjectTransport(), timeout=15, follow_redirects=False
        ) as http:
            application.state.engine, application.state.http = engine, http
            application.state.verifier = SyntheticVerifier(settings, cfg, http, user_ids)
            application.state.auth_admin = AuthAdmin(settings, http)
            application.state.storage = SyntheticStorage(
                settings, cfg, http, manifest_path, user_ids
            )
            application.state.run_tasks = set()
            try:
                # Constructor only: Voyage does not make requests until search. Search stays blocked.
                configured = (
                    build_knowledge_retriever(engine, settings, cfg)
                    if settings.voyage_api_key
                    else None
                )
                application.state.knowledge = BlockPaidRetrieval(engine, configured)
                runtime = build_e2e_runtime(cfg)
                application.state.runtime = runtime
                yield
            finally:
                for task in list(application.state.run_tasks):
                    task.cancel()
                await asyncio.gather(*application.state.run_tasks, return_exceptions=True)
                if runtime is not None and runtime.openai_client is not None:
                    await runtime.openai_client.close()
                await engine.dispose()

    # Replace BEFORE entering anything: no purge/reconcile tasks or real OpenAI client is ever created.
    app.router.lifespan_context = lifespan

    @app.middleware("http")
    async def block_global_case_purge(request, call_next):
        if request.method == "DELETE" and re.fullmatch(
            r"/v1/cases/[0-9a-f-]{36}", request.url.path
        ):
            return envelope(
                request,
                "hosted_global_maintenance_blocked",
                "Individual case deletion invokes global maintenance and is disabled in the hosted synthetic seam. Account cleanup remains scoped.",
                403,
            )
        return await call_next(request)

    @app.get("/hosted-product/preflight", include_in_schema=False)
    async def preflight():
        async with app.state.engine.connect() as connection:
            result = {}
            for name in RELATIONS:
                result[name] = bool(
                    await connection.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname || '.' || c.relname = :name)"
                        ),
                        {"name": name},
                    )
                )
        return {
            "project_ref": data["project_ref"],
            "relations": result,
            "model": "scripted",
            "paid_retrieval": "blocked",
            "maintenance": "disabled",
        }

    return app
