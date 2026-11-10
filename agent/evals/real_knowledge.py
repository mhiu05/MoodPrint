"""Explicit local, metered PgVector factory for synthetic paid eval continuation.

Injected into evals/run.py via --retriever-factory evals.real_knowledge:factory.
Never creates an authorization or ledger, never accepts hosted database URLs.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import dotenv_values
from moodprint_agent.knowledge.embedder import VoyageEmbedder
from moodprint_agent.knowledge.ingest.budget import commit, reserve
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import AppConfig
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


def local_database() -> str:
    values = dotenv_values(
        Path(os.environ.get("MOODPRINT_EVAL_DATABASE_ENV", ".local/stacks/int/test.env"))
    )
    database = values.get("TEST_DATABASE_URL")
    if not database or make_url(database).host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("real evaluation requires an explicit loopback database")
    return database


class MeteredQueryEmbedder:
    def __init__(self, inner: VoyageEmbedder, ledger: Path):
        self.inner, self.ledger = inner, ledger
        self._lock = asyncio.Lock()

    async def embed_query(self, value: str) -> list[float]:
        async with self._lock:
            return await self._embed_one(value)

    async def _embed_one(self, value: str) -> list[float]:
        # One byte is a conservative tokenizer upper bound. Include five attempts.
        reservation = reserve(max(1, len(value.encode("utf-8")) * 5), ledger=self.ledger)
        before_attempts, before_calls = self.inner.attempts, self.inner.usage.calls
        before_tokens = self.inner.usage.total_tokens
        try:
            return await self.inner.embed_query(value)
        finally:
            known = (
                self.inner.attempts - before_attempts == self.inner.usage.calls - before_calls
                and self.inner.settlement_tokens is not None
            )
            commit(
                reservation,
                self.inner.usage.total_tokens - before_tokens if known else None,
                ledger=self.ledger,
            )


def configuration() -> tuple[str, Path, str]:
    database = local_database()
    ledger = Path(os.environ.get("MOODPRINT_VOYAGE_LEDGER", ".local/voyage-ledger.json"))
    if not ledger.is_file() or not ledger.with_suffix(".jsonl").is_file():
        raise ValueError("existing cumulative Voyage ledger and log required")
    authorization = json.loads(ledger.read_text(encoding="utf-8"))
    if authorization.get("model") != "voyage-4" or authorization.get("scope") != "phase-2-voyage":
        raise ValueError("Voyage authorization model/scope mismatch")
    key = dotenv_values(Path(os.environ.get("MOODPRINT_VOYAGE_KEY_FILE", ".env"))).get(
        "VOYAGE_API_KEY"
    )
    if not key:
        raise ValueError("Voyage credentials unavailable")
    return database, ledger, key


@asynccontextmanager
async def factory(cfg: AppConfig, corpus_version: str):
    database, ledger, key = await asyncio.to_thread(configuration)
    engine = create_async_engine(database, hide_parameters=True)
    voyage = VoyageEmbedder(key, cfg.knowledge)
    try:
        async with engine.connect() as conn, conn.begin():
            await conn.execute(text("set local role authenticated"))
            row = (
                (
                    await conn.execute(
                        text(
                            "select version,embedding_model,manifest_sha256 from knowledge.corpus_versions where status='published'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            expected = os.environ.get("MOODPRINT_EVAL_CORPUS_SHA256")
            if (
                row["version"] != corpus_version
                or row["embedding_model"] != "voyage-4"
                or (expected and row["manifest_sha256"] != expected)
            ):
                raise ValueError("published real corpus does not match the pinned evaluation")
        yield PgVectorKnowledgeRetriever(
            engine, MeteredQueryEmbedder(voyage, ledger), cfg.knowledge
        )
    finally:
        await voyage.aclose()
        await engine.dispose()
