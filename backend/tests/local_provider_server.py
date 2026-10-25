"""Opt-in live smoke entrypoint. Never imported by app or deterministic tests."""

import asyncio
import os

import uvicorn
from dotenv import dotenv_values
from fastapi import Depends, Request
from pydantic import SecretStr
from sqlalchemy import func, select

from app.ai import embeddings
from app.ai.embedding_models import MemoryEmbedding
from app.ai.voyage import EmbeddingError, VoyageProvider
from app.core.errors import DomainError
from app.core.security import Actor, assert_purpose, require_actor, transaction
from tests.e2e_server import app, seed  # validates local *_test DB and sanitizes env

if os.environ.get("MOODPRINT_ALLOW_LIVE_OPENAI") != "true":
    raise RuntimeError("Live provider calls need explicit opt-in")

values = dotenv_values(os.environ["MOODPRINT_PROVIDER_ENV"])
settings = app.state.settings
# Allowlist only the provider configuration; never inherit hosted DB/Auth/SMTP.
settings.openai_api_key = SecretStr(values.get("OPENAI_API_KEY") or "")
settings.openai_model = values.get("OPENAI_MODEL") or ""
settings.ai_enabled = True
settings.ai_accounting_enabled = False
settings.provider_force_ipv4 = (values.get("PROVIDER_FORCE_IPV4") or "false").lower() == "true"
app.state.ai.model_override = None
if not app.state.ai.available:
    raise RuntimeError("Supply valid local OPENAI_API_KEY and OPENAI_MODEL configuration")

metrics = {
    "openaiRequests": 0,
    "inputTokens": 0,
    "outputTokens": 0,
    "voyageRequests": 0,
    "voyageQueriesSucceeded": 0,
    "voyageDocumentsSucceeded": 0,
}
model_limit = int(os.environ.get("MOODPRINT_SMOKE_OPENAI_LIMIT", "8"))
voyage_limit = int(os.environ.get("MOODPRINT_SMOKE_VOYAGE_LIMIT", "4"))
if not 1 <= model_limit <= 8 or not 1 <= voyage_limit <= 4:
    raise RuntimeError("Local smoke budget must stay within 8 model / 4 embedding requests")


async def observe(event):
    if event.kind == "request_started":
        if metrics["openaiRequests"] >= model_limit:
            raise DomainError(429, "SMOKE_BUDGET", "Local smoke request budget reached")
        metrics["openaiRequests"] += 1
    if event.kind == "response_received":
        metrics["inputTokens"] += event.input_tokens
        metrics["outputTokens"] += event.output_tokens


app.state.ai.provider.usage_observer = observe


class BoundedVoyage(VoyageProvider):
    async def embed(self, text, input_type):
        if metrics["voyageRequests"] >= voyage_limit:
            raise EmbeddingError("local_smoke_budget_reached")
        metrics["voyageRequests"] += 1
        result = await super().embed(text, input_type)
        metrics[
            "voyageQueriesSucceeded" if input_type == "query" else "voyageDocumentsSucceeded"
        ] += 1
        return result


if os.environ.get("MOODPRINT_ALLOW_LIVE_VOYAGE") == "true":
    settings.voyage_api_key = SecretStr(values.get("VOYAGE_API_KEY") or "")
    if not settings.voyage_api_key.get_secret_value():
        raise RuntimeError("Voyage smoke requires VOYAGE_API_KEY")
    settings.voyage_model = values.get("VOYAGE_MODEL") or "voyage-4-lite"
    settings.voyage_dimensions = int(values.get("VOYAGE_DIMENSIONS") or "1024")
    settings.semantic_memory_enabled = True
    embeddings.VoyageProvider = BoundedVoyage


@app.get("/api/v1/__local_smoke/status")
async def status(actor: Actor = Depends(require_actor)):
    async with app.state.database.sessions() as db:
        indexed = await db.scalar(
            select(func.count())
            .select_from(MemoryEmbedding)
            .where(MemoryEmbedding.user_id == actor.user_id)
        )
        version = await db.scalar(
            select(func.max(MemoryEmbedding.memory_version)).where(
                MemoryEmbedding.user_id == actor.user_id
            )
        )
    return {
        **metrics,
        "indexedMemories": indexed,
        "indexedVersion": version,
        "realOpenAI": True,
        "voyageEnabled": settings.semantic_memory_enabled,
    }


@app.post("/api/v1/__local_smoke/retrieve")
async def retrieve(request: Request, actor: Actor = Depends(require_actor)):
    # Test-only aggregate probe: real authorization and retriever; never expose text.
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
        await assert_purpose(db, user, "MEM")
        version = user.data_version
    memories = await embeddings.retrieve_memories(
        app.state.database, settings, actor, "guong", "vẽ tranh bằng màu nước", version
    )
    return {"memoriesRetrieved": len(memories)}


if __name__ == "__main__":
    if os.environ.get("MOODPRINT_SMOKE_RESUME") != "true":
        asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
    uvicorn.run(
        app, host="127.0.0.1", port=8002, loop="app.core.loop:selector_factory", log_config=None
    )
