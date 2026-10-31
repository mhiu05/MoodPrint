"""P2-09 performance: collaborative vs single-agent turn latency on synthetic models.

Opt-in (MOODPRINT_COLLAB_LOAD=1): it takes minutes. Models are synthetic with fixed latency
(primary 1.5 s, specialist 1.0 s), so the numbers measure orchestration overhead (DB
transactions, authorization, receipts) plus the configured model time — not provider speed.
Results are written to MOODPRINT_COLLAB_LOAD_OUT (JSON) and printed.
"""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import pytest

from tests.collaboration_helpers import HABIT, finish, setup, start
from tests.conftest import add_actor
from tests.fakes import ScriptedModel, message_output
from tests.test_multi_message_persistence import conversation

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(os.getenv("MOODPRINT_COLLAB_LOAD") != "1",
                                                       reason="opt-in load measurement")]
PRIMARY_SECONDS, SPECIALIST_SECONDS = 1.5, 1.0
USERS = int(os.getenv("MOODPRINT_COLLAB_USERS", "8"))
TURNS = 5
# Production pool per API process (5 + 2); the test fixture's default engine would hide waits.
POOL = (int(os.getenv("MOODPRINT_COLLAB_POOL", "5")), int(os.getenv("MOODPRINT_COLLAB_OVERFLOW", "2")))


class Delayed(ScriptedModel):
    def __init__(self, payload, seconds, *, fail=False):
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        super().__init__([[message_output(text)]])
        self.seconds, self.fail = seconds, fail

    async def stream_response(self, *args, **kwargs):
        await asyncio.sleep(self.seconds)
        async for event in super().stream_response(*args, **kwargs):
            yield event


def pct(values, q):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))], 3)


async def scenario(app, actors, *, text, specialist, enabled=True):
    app.state.settings.ai_collaboration_enabled = enabled
    app.state.ai.specialist_model_override = specialist
    primary = Delayed({"messages": [{"text": "Thương ghê, thử nghỉ sớm nhé.", "cards": []}]}, PRIMARY_SECONDS)
    app.state.ai.model_override = primary
    durations, peak = [], 0
    pool = app.state.database.engine.pool
    stop = asyncio.Event()

    async def sample():
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, pool.checkedout())
            await asyncio.sleep(0.02)

    sampler = asyncio.create_task(sample())

    async def user(client):
        url = await conversation(client, "may")
        for _ in range(TURNS):
            began = time.monotonic()
            run = await finish(await start(app, client, url, text))
            assert run.terminal_status == "completed", run.failure
            durations.append(time.monotonic() - began)

    await asyncio.gather(*(user(client) for client, _ in actors))
    stop.set()
    await sampler
    calls = len(primary.calls) + (len(specialist.calls) if specialist else 0)
    return {"turns": len(durations), "p50": pct(durations, 0.5), "p95": pct(durations, 0.95),
            "p99": pct(durations, 0.99), "mean": round(statistics.mean(durations), 3),
            "modelCallsPerTurn": round(calls / len(durations), 2), "peakDbConnections": peak}


async def test_collaboration_latency_overhead(clients):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    app, base = clients
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], pool_size=POOL[0], max_overflow=POOL[1],
                                 pool_timeout=10, connect_args={"prepare_threshold": None})
    fixture_engine = app.state.database.engine
    app.state.database.engine = engine
    app.state.database.sessions = async_sessionmaker(engine, expire_on_commit=False)
    actors = list(base)
    for index in range(2, USERS):
        actors.append(await add_actor(app, 20 + index))
    for client, _ in actors:
        await setup(app, client, edges=("nhip_habit_for_may",), journal=False)
    app.state.settings.ai_user_concurrency = 2
    app.state.settings.ai_daily_turns_per_user = 1000
    app.state.settings.ai_requests_per_minute = 120
    app.state.settings.ai_collaboration_daily_cap = 50
    habit = Delayed(HABIT, SPECIALIST_SECONDS)
    results = {
        "single_agent": await scenario(app, actors, text="Chào Mây, hôm nay ổn không", specialist=Delayed(HABIT, 0)),
        "collaborative": await scenario(app, actors, text="Mấy hôm nay mình mất ngủ", specialist=habit),
        "collaboration_disabled": await scenario(app, actors, text="Mấy hôm nay mình mất ngủ",
                                                 specialist=Delayed(HABIT, 0), enabled=False),
        "specialist_invalid_fallback": await scenario(app, actors, text="Mấy hôm nay mình mất ngủ",
                                                      specialist=Delayed({"x": 1}, SPECIALIST_SECONDS)),
    }
    results["config"] = {"users": USERS, "turnsPerUser": TURNS, "primarySeconds": PRIMARY_SECONDS,
                         "specialistSeconds": SPECIALIST_SECONDS, "pool": {"size": POOL[0], "overflow": POOL[1]}}
    app.state.database.engine = fixture_engine
    app.state.database.sessions = async_sessionmaker(fixture_engine, expire_on_commit=False)
    await engine.dispose()
    overhead = results["collaborative"]["p95"] - results["single_agent"]["p95"]
    results["p95OverheadSeconds"] = round(overhead, 3)
    print(json.dumps(results, indent=2))
    if os.getenv("MOODPRINT_COLLAB_LOAD_OUT"):
        await asyncio.to_thread(Path(os.environ["MOODPRINT_COLLAB_LOAD_OUT"]).write_text,
                                json.dumps(results, indent=2), encoding="utf-8")
    # P2-NFR-01: collaboration adds at most 4 s at p95 (here: 1 s of synthetic specialist time).
    assert overhead <= 4.0
    assert results["collaboration_disabled"]["modelCallsPerTurn"] == 1.0
    assert results["single_agent"]["modelCallsPerTurn"] == 1.0
    assert results["collaborative"]["modelCallsPerTurn"] == 2.0

