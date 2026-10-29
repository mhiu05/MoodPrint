"""Loopback-only guest workload entrypoint. Importing e2e_server validates/sanitizes the target."""

import asyncio
import json
import os
import time
from datetime import timedelta

import uvicorn
from openai.types.responses import ResponseCompletedEvent
from sqlalchemy import func, select, text, update

from app.core.security import digest
from app.infrastructure.database.models import AuthSession, User
from tests.e2e_server import app
from tests.e2e_server import seed as seed_registered
from tests.fakes import ScriptedModel, completed_response, message_output
from tests.guest_helpers import LIFETIME, add_guest

COUNTERS = {"aiCalls": 0, "aiActive": 0, "aiPeak": 0, "voiceCalls": 0, "voiceActive": 0, "voicePeak": 0}


class GuestLoadModel(ScriptedModel):
    async def stream_response(self, *args, **kwargs):
        COUNTERS["aiCalls"] += 1
        COUNTERS["aiActive"] += 1
        COUNTERS["aiPeak"] = max(COUNTERS["aiPeak"], COUNTERS["aiActive"])
        try:
            await asyncio.sleep(60 if "HOLD-FOR-CRASH" in json.dumps(args[1]) else 0.5)
            yield ResponseCompletedEvent(response=completed_response([message_output('{"text":"Synthetic guest completion","cards":[]}')]), sequence_number=1, type="response.completed")
        finally:
            COUNTERS["aiActive"] -= 1


class GuestTranscriber:
    async def transcribe(self, data):
        COUNTERS["voiceCalls"] += 1
        COUNTERS["voiceActive"] += 1
        COUNTERS["voicePeak"] = max(COUNTERS["voicePeak"], COUNTERS["voiceActive"])
        try:
            await asyncio.sleep(0.5)
            return "Synthetic voice preview"
        finally:
            COUNTERS["voiceActive"] -= 1


app.state.ai.model_override = GuestLoadModel([])
app.state.transcriber = GuestTranscriber()
app.state.settings.guest_ai_per_minute = 6
app.state.settings.guest_voice_per_minute = 2


def rss_bytes():
    if os.name != "nt":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    import ctypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong),
                    *[(name, ctypes.c_size_t) for name in ("peak", "working", "qpp", "qp", "qnp", "qn", "page", "pagepeak")]]
    values = Counters()
    values.cb = ctypes.sizeof(values)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = ctypes.c_void_p
    get = ctypes.windll.psapi.GetProcessMemoryInfo
    get.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not get(current(), ctypes.byref(values), values.cb):
        raise RuntimeError("RSS sampling unavailable")
    return values.working


@app.get("/__synthetic/stats", include_in_schema=False)
async def stats():
    from app.modules.guests.jobs import guest_metrics
    from app.modules.guests.models import GuestBudgetDay
    pool = app.state.database.engine.pool
    before = time.perf_counter()
    async with app.state.database.engine.connect():
        pool_wait = (time.perf_counter() - before) * 1000
    async with app.state.database.sessions() as db:
        guests = await db.scalar(select(func.count()).select_from(User).where(User.account_kind == "guest"))
        connections = await db.scalar(text("select count(*) from pg_stat_activity where datname=current_database()"))
        liability = await db.scalar(select(func.coalesce(func.sum(GuestBudgetDay.spent_nano_usd + GuestBudgetDay.reserved_nano_usd), 0)))
        backlog = await db.scalar(text("select count(*) from moodprint.memory_embedding_jobs where status in ('pending','running','retry')"))
        running = await db.scalar(text("select count(*) from moodprint.ai_runs where status='running'"))
    return {**COUNTERS, **await guest_metrics(app), "guests": guests, "connections": connections,
            "poolCheckedOut": pool.checkedout(), "rssBytes": rss_bytes(), "liabilityNanoUsd": int(liability),
            "sseOpen": app.state.ai.streams.open(), "poolWaitMs": pool_wait,
            "embeddingBacklog": backlog, "runningAi": running}


async def seed(count=50):
    await seed_registered()
    deadlines = []
    for number in range(count):
        guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=90), consents=False)
        async with app.state.database.sessions.begin() as db:
            await db.execute(update(AuthSession).where(AuthSession.id == guest.session_id).values(
                token_hash=digest(f"guest-load-session-{number}"), csrf_hash=digest(f"guest-load-csrf-{number}")))
        deadlines.append(guest.expires_at)
        await guest.client.aclose()
    await app.state.database.engine.dispose()
    return max(deadlines)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MOODPRINT_GUEST_LOAD_PORT", "8018")),
                loop="app.core.loop:selector_factory", log_config=None)
