"""Two-worker local load fixture. Only synthetic input; never import from production."""
# ruff: noqa: E402 -- sanitize configuration before importing application modules

import asyncio
import ctypes
import json
import os
import re
import sys
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tests.database_target import require_local_test_database

DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
require_local_test_database(DATABASE_URL)
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "",
        "DATABASE_MIGRATION_URL": "",
        "SUPABASE_URL": "",
        "SUPABASE_PUBLISHABLE_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
        "VOYAGE_API_KEY": "",
        "SEMANTIC_MEMORY_ENABLED": "false",
    }
)

import uvicorn
from agents import Model
from agents.items import ModelResponse, TResponseStreamEvent
from openai.types.responses import ResponseCompletedEvent, ResponseTextDeltaEvent
from pydantic import SecretStr
from sqlalchemy import select, text

import app.ai.embeddings as embeddings
from app.ai import embedding_models  # noqa: F401 -- register vector tables
from app.ai.memory_models import MemoryProposal
from app.ai.models import AiPreference
from app.core.config import Settings
from app.core.security import digest
from app.infrastructure.database.models import AuthSession, Base, Consent, Memory, User, now
from app.main import create_app
from app.modules.guests import models as guest_models  # noqa: F401 -- register before reset
from tests.fakes import completed_response, message_output
from tests.feedback_schema import install_feedback_functions
from tests.guest_schema import install_auth_fixture, install_guest_guards

COUNTERS = {
    "sdk_calls": 0,
    "sdk_active": 0,
    "sdk_peak": 0,
    "isolation_failures": 0,
    "missing_memory": 0,
    "query_calls": 0,
    "document_calls": 0,
    "cancelled_calls": 0,
}
# Actors whose synthetic turn is currently held open, so the driver can cancel or
# kill exactly that worker. Numbers only; never prompts or memory text.
HELD: set[str] = set()


def identity(kind: str, number: int):
    return uuid5(NAMESPACE_URL, f"moodprint-synthetic-load:{kind}:{number}")


class SyntheticVoyage:
    def __init__(self, settings: Settings):
        self.dimensions = settings.voyage_dimensions

    async def embed(self, value: str, input_type: str) -> list[float]:
        COUNTERS["query_calls" if input_type == "query" else "document_calls"] += 1
        await asyncio.sleep(0.002)
        # Every document is equally close, so missing owner/bot filters is detectable.
        return [1.0] + [0.0] * (self.dimensions - 1)


class LoadModel(Model):
    """Actual Agents SDK Model contract, with no retained prompts or request history."""

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise AssertionError("SDK streaming is required")

    async def stream_response(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[TResponseStreamEvent]:
        COUNTERS["sdk_calls"] += 1
        COUNTERS["sdk_active"] += 1
        COUNTERS["sdk_peak"] = max(COUNTERS["sdk_peak"], COUNTERS["sdk_active"])
        try:
            serialized = json.dumps(args[1], ensure_ascii=False)
            actor_match = re.findall(r"LOAD_ACTOR:(\d{3}) BOT:(\w+)", serialized)
            memory_matches = re.findall(r"MEMORY_ACTOR:(\d{3}) BOT:(\w+)", serialized)
            expected = actor_match[-1] if actor_match else None
            if not expected or any(match != expected for match in memory_matches):
                COUNTERS["isolation_failures"] += 1
                raise AssertionError("synthetic memory isolation violated")
            # A personal consent write does not withdraw approved memory.
            if not memory_matches:
                COUNTERS["missing_memory"] += 1
                raise AssertionError("indexed memory was not retrieved")
            if "HOLD" in serialized:
                HELD.add(expected[0])
                try:
                    await asyncio.sleep(float(os.environ.get("MOODPRINT_LOAD_HOLD_SECONDS", "15")))
                except asyncio.CancelledError:
                    COUNTERS["cancelled_calls"] += 1
                    raise
                finally:
                    HELD.discard(expected[0])
            await asyncio.sleep(float(os.environ.get("MOODPRINT_LOAD_MODEL_DELAY", "0.2")))
            yield ResponseTextDeltaEvent(
                content_index=0,
                delta="RAW-SYNTHETIC-CANARY",
                item_id="load",
                logprobs=[],
                output_index=0,
                sequence_number=0,
                type="response.output_text.delta",
            )
            output = json.dumps(
                {"text": f"Synthetic completion actor {expected[0]} bot {expected[1]}", "cards": []}
            )
            yield ResponseCompletedEvent(
                response=completed_response([message_output(output)]),
                sequence_number=1,
                type="response.completed",
            )
        finally:
            COUNTERS["sdk_active"] -= 1


settings = Settings(
    _env_file=None,
    app_env="test",
    database_url=SecretStr(DATABASE_URL),
    ai_enabled=True,
    chat_history_enabled=True,
    ai_global_concurrency=50,
    database_pool_size=int(os.environ.get("MOODPRINT_LOAD_POOL_SIZE", "5")),
    database_pool_overflow=int(os.environ.get("MOODPRINT_LOAD_POOL_OVERFLOW", "5")),
    database_pool_timeout=10,
    ai_timeout_seconds=float(os.environ.get("MOODPRINT_LOAD_AI_TIMEOUT", "30")),
    semantic_memory_enabled=True,
    voyage_api_key=SecretStr("synthetic-fixture-only"),
    voyage_dimensions=256,
    embedding_job_batch_size=50,
)
embeddings.VoyageProvider = SyntheticVoyage  # type: ignore[misc, assignment]
app = create_app(settings)
app.state.ai.model_override = LoadModel()
if os.environ.get("MOODPRINT_DEBUG_STACKS"):
    import faulthandler

    _stacks = open(  # noqa: SIM115 -- kept open for the delayed dump
        Path(os.environ["MOODPRINT_DEBUG_STACKS"]) / f"stacks-{os.getpid()}.txt", "w"
    )
    faulthandler.dump_traceback_later(40, file=_stacks)


def rss_bytes() -> int:
    if sys.platform == "win32":

        class MemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                *[
                    (name, ctypes.c_size_t)
                    for name in (
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                    )
                ],
            ]

        counts = MemoryCounters()
        counts.cb = ctypes.sizeof(counts)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(MemoryCounters), ctypes.c_ulong]
        get_memory.restype = ctypes.c_int
        if not get_memory(get_process(), ctypes.byref(counts), counts.cb):
            raise RuntimeError("synthetic RSS instrumentation unavailable")
        return int(counts.WorkingSetSize)
    import resource

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)


@app.middleware("http")
async def worker_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Synthetic-Worker"] = str(app.state.ai.worker_id)
    return response


@app.get("/__synthetic_load_stats")
async def stats():
    pool = app.state.database.engine.pool
    return {
        "pid": os.getpid(),
        "rss_bytes": rss_bytes(),
        "pool_checked_out": pool.checkedout(),
        "pool_size": pool.size(),
        "pool_overflow": pool.overflow(),
        "runtime_worker_id": str(app.state.ai.worker_id),
        "held": sorted(HELD),
        **COUNTERS,
    }


async def seed(count: int):
    # Only the parent driver invokes this, once, before either server worker starts.
    async with app.state.database.engine.begin() as connection:
        await connection.execute(text("create schema if not exists moodprint"))
        await connection.execute(text("create schema if not exists extensions"))
        await connection.execute(
            text("create extension if not exists vector with schema extensions")
        )
        await connection.run_sync(Base.metadata.drop_all)
        # The feedback CHECK constraints call private functions that must exist first.
        await install_feedback_functions(connection)
        await connection.run_sync(Base.metadata.create_all)
        await install_guest_guards(connection)
        await install_auth_fixture(connection)
    async with app.state.database.sessions.begin() as db:
        for number in range(count):
            uid, sid = identity("user", number), identity("provider", number)
            db.add(
                User(id=uid, auth_subject=uid, alias=f"Synthetic actor {number}", age_band="adult")
            )
            await db.flush()
            db.add(
                AuthSession(
                    id=identity("session", number),
                    user_id=uid,
                    token_hash=digest(f"load-session-{number}"),
                    csrf_hash=digest(f"load-csrf-{number}"),
                    provider_session_id=sid,
                    expires_at=now() + timedelta(hours=1),
                )
            )
            db.add(AiPreference(user_id=uid, history_enabled=True, semantic_memory_enabled=True))
            for purpose in ("AI", "MEM", "VOICE", "MATCH"):
                db.add(Consent(user_id=uid, purpose=purpose, enabled=purpose in ("AI", "MEM")))
            for bot in ("may", "guong"):
                db.add(
                    Memory(
                        user_id=uid,
                        bot_id=bot,
                        text=f"MEMORY_ACTOR:{number:03d} BOT:{bot} approved preference",
                        proposal_id=identity(f"approved-{bot}", number),
                    )
                )
            db.add(
                MemoryProposal(
                    id=identity("pending", number),
                    user_id=uid,
                    bot_id="may",
                    text=f"MEMORY_ACTOR:{number:03d} BOT:may preview preference",
                    data_version=1,
                    ai_consent_version=1,
                    mem_consent_version=1,
                    expires_at=now() + timedelta(minutes=15),
                )
            )
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:sid,:uid)"),
                {"sid": sid, "uid": uid},
            )


async def index_seeded_memories():
    async with app.state.database.sessions.begin() as db:
        for memory in (await db.scalars(select(Memory))).all():
            await embeddings.enqueue_memory(db, memory, settings)
    for _ in range(20):
        count = await embeddings.process_embedding_jobs(
            app.state.database, settings, provider=SyntheticVoyage(settings)
        )
        if not count:
            break


if __name__ == "__main__":
    uvicorn.run(
        "tests.chat_load_server:app",
        host="127.0.0.1",
        port=int(os.environ.get("MOODPRINT_LOAD_PORT", "8003")),
        workers=int(os.environ.get("MOODPRINT_LOAD_WORKERS", "2")),
        loop="app.core.loop:selector_factory",
        log_level=os.environ.get("MOODPRINT_LOAD_LOG_LEVEL", "warning"),
        access_log=False,
    )
