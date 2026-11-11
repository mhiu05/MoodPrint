"""Genuine local FastAPI runtime with bounded, metered real provider clients.

No routes, jobs, approvals, storage behavior or retriever are replaced. Both
provider ledgers must already exist; the task authorization caps are enforced
again before the application is constructed. Never run this on a public host.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import httpx
from app.main import create_app as real_app
from openai import AsyncOpenAI
from safevoice_agent.knowledge.embedder import EmbeddingCache, VoyageEmbedder
from safevoice_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from safevoice_shared.config import AppConfig
from safevoice_shared.env import EnvSettings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from evals.budget import BudgetLedger, GuardedTransport, load_budget  # noqa: E402

from scripts.hosted_product import load_values  # noqa: E402
from scripts.live_providers import DefaultTierTransport, RecordingTransport, VoyageTransport  # noqa: E402


class CachedQueryEmbedder:
    """Cache only actual Voyage query vectors with exact model/dims/text keys."""

    def __init__(self, real: VoyageEmbedder, cache: EmbeddingCache, cfg):
        self.real, self.cache, self.cfg = real, cache, cfg

    async def embed_query(self, text: str) -> list[float]:
        model, dims = self.cfg.resolved_query_model(), self.cfg.embedding_dims
        digest = hashlib.sha256(text.encode()).hexdigest()
        cached = self.cache.get(model, dims, "query", digest)
        if cached is not None:
            return cached
        vector = await self.real.embed_query(text)
        self.cache.put(model, dims, "query", digest, vector)
        return vector


def _existing_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value or not Path(value).is_file():
        raise ValueError(f"{name} must point to the existing owner-managed cumulative file")
    return Path(value).resolve()


def create_app():
    values = load_values()
    settings = EnvSettings(**values)
    if settings.app_env != "development":
        raise ValueError("Live MVP inspection is authorized only in local development")
    if not settings.openai_api_key or not settings.voyage_api_key:
        raise ValueError("The existing owner provider keys are required")
    budget_path = _existing_path("SAFEVOICE_EVAL_BUDGET")
    ledger_path = _existing_path("SAFEVOICE_EVAL_LEDGER")
    voyage_path = _existing_path("SAFEVOICE_VOYAGE_LEDGER")
    budget = load_budget(budget_path, scope="phase3-eval")
    if budget.max_usd > 2.99 or budget.max_calls_total > 1140:
        raise ValueError("Live MVP authorization exceeds this task's cumulative caps")
    ledger = BudgetLedger(budget, ledger_path)
    if ledger.reserved_calls >= budget.max_calls_total or ledger.committed_usd >= budget.max_usd:
        raise ValueError("The cumulative provider budget is exhausted")
    output = ROOT / ".local/fresh-supabase"
    output.mkdir(parents=True, exist_ok=True)
    cfg = AppConfig()
    run_id = f"fresh-supabase-mvp-{uuid4().hex[:12]}"
    voyage_http = httpx.AsyncClient(transport=VoyageTransport(voyage_path), timeout=20)
    cache = EmbeddingCache(output / "query-cache.sqlite")

    def model_factory(actual_settings):
        guarded = GuardedTransport(httpx.AsyncHTTPTransport(trust_env=False), ledger, run_id=run_id)
        http = httpx.AsyncClient(
            transport=RecordingTransport(
                DefaultTierTransport(guarded), output / "model-http.jsonl"
            ),
            timeout=90,
        )
        return AsyncOpenAI(
            api_key=actual_settings.openai_api_key.get_secret_value(),
            http_client=http,
            max_retries=0,
        )

    def knowledge_factory(engine, actual_settings, actual_cfg):
        real = VoyageEmbedder(
            actual_settings.voyage_api_key.get_secret_value(),
            actual_cfg.knowledge,
            client=voyage_http,
        )
        return PgVectorKnowledgeRetriever(
            engine, CachedQueryEmbedder(real, cache, actual_cfg.knowledge), actual_cfg.knowledge
        )

    app = real_app(
        settings, cfg, model_client_factory=model_factory, knowledge_factory=knowledge_factory
    )
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def metered_lifespan(actual_app):
        try:
            async with original_lifespan(actual_app):
                yield
        finally:
            cache.close()
            await voyage_http.aclose()

    app.router.lifespan_context = metered_lifespan
    (output / "runtime-composition.json").write_text(
        json.dumps(
            {
                "runtime": "app.main:create_app",
                "model": cfg.agent.companion_model,
                "retriever": "PgVectorKnowledgeRetriever",
                "embedding_model": "voyage-4",
                "scripted_model": False,
                "background_jobs_enabled": True,
                "model_judge": None,
                "max_usd_cumulative": budget.max_usd,
                "max_calls_cumulative": budget.max_calls_total,
                "run_id": run_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return app
