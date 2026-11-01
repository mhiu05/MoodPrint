"""V3 performance: single agent vs planner vs as_tool vs handoff vs group, on synthetic models.

Opt-in (MOODPRINT_V3_LOAD=1): it takes minutes. Every synthetic model call (planner, Điều phối,
specialists, handoff target, group speakers) takes MOODPRINT_V3_CALL_SECONDS (default 1.0 s), so
the numbers measure orchestration overhead (transactions, authorization, receipts, child runs)
plus the configured model time — not provider speed. Results go to MOODPRINT_V3_LOAD_OUT (JSON).
"""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from tests.conftest import add_actor
from tests.mood_e2e_model import MoodE2EModel
from tests.orchestration_helpers import key, v3_setup

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(os.getenv("MOODPRINT_V3_LOAD") != "1",
                                                       reason="opt-in load measurement")]
CALL_SECONDS = float(os.getenv("MOODPRINT_V3_CALL_SECONDS", "1.0"))
USERS = int(os.getenv("MOODPRINT_V3_USERS", "8"))
TURNS = int(os.getenv("MOODPRINT_V3_TURNS", "5"))
POOL = (5, 2)


def pct(values, q):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))], 3)


async def wait(app, run_id):
    run = app.state.ai.runs[UUID(run_id)]
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 120)
    return run


async def direct_turn(app, client, url, text):
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", headers=key(), json={
        "text": text, "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]})
    assert accepted.status_code == 202, accepted.text
    return await wait(app, accepted.json()["runId"])


async def group_turn(app, client, url, text):
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", headers=key(), json={
        "text": text, "clientMessageId": str(uuid4()), "expectedVersion": view["version"], "mentions": []})
    assert accepted.status_code == 202, accepted.text
    return await wait(app, accepted.json()["turnId"])


async def scenario(app, actors, model, *, kind, text, fresh_each_turn=False):
    durations, peak, checkout = [], 0, []
    pool = app.state.database.engine.pool
    stop = asyncio.Event()
    calls_before = len(model.calls)

    async def sample():
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, pool.checkedout())
            began = time.monotonic()
            async with app.state.database.sessions() as db:
                await db.connection()
            checkout.append(time.monotonic() - began)
            await asyncio.sleep(0.05)

    sampler = asyncio.create_task(sample())

    async def user(client):
        url = None
        for _ in range(TURNS):
            if url is None or fresh_each_turn:
                if kind == "group":
                    created = await client.post("/api/v1/ai/groups", headers=key(),
                                                json={"name": "Đo tải", "members": ["nhatky", "hoatdong"]})
                    url = f"/api/v1/ai/groups/{created.json()['groupId']}"
                else:
                    created = await client.post("/api/v1/ai/conversations", headers=key(),
                                                json={"botId": "dieuphoi" if kind != "legacy" else "may"})
                    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
            began = time.monotonic()
            run = await (group_turn if kind == "group" else direct_turn)(app, client, url, text)
            assert run.terminal_status == "completed", run.failure
            durations.append(time.monotonic() - began)

    await asyncio.gather(*(user(client) for client, _ in actors))
    stop.set()
    await sampler
    calls = len(model.calls) - calls_before
    return {"turns": len(durations), "p50": pct(durations, 0.5), "p95": pct(durations, 0.95),
            "p99": pct(durations, 0.99), "mean": round(statistics.mean(durations), 3),
            "modelCallsPerTurn": round(calls / len(durations), 2), "peakDbConnections": peak,
            "dbCheckoutP95Ms": round(pct(checkout, 0.95) * 1000, 1) if checkout else None}


async def test_v3_latency_by_workflow(clients):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    app, base = clients
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], pool_size=POOL[0], max_overflow=POOL[1],
                                 pool_timeout=10, connect_args={"prepare_threshold": None})
    fixture_engine = app.state.database.engine
    app.state.database.engine = engine
    app.state.database.sessions = async_sessionmaker(engine, expire_on_commit=False)
    actors = list(base)
    for index in range(2, USERS):
        actors.append(await add_actor(app, 30 + index))
    for client, _ in actors:
        await v3_setup(app, client, edges=("dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong",
                                           "dieuphoi_handoff_nhatky"), journal=True)
    settings = app.state.settings
    settings.ai_group_chat_enabled = True
    settings.ai_user_concurrency = 2
    settings.ai_daily_turns_per_user = 1000
    settings.ai_requests_per_minute = 120
    settings.ai_orchestration_daily_cap = 100
    settings.ai_timeout_seconds = 60
    model = MoodE2EModel([])
    model.v3_delay = CALL_SECONDS
    app.state.ai.model_override = model
    app.state.ai.agent_model_overrides = {}
    results = {
        "single_agent": await scenario(app, actors, model, kind="direct", text="Chào Điều phối"),
        "planner_then_direct": await scenario(app, actors, model, kind="direct",
                                              text="Mình muốn lên kế hoạch cho tuần tới"),
        "as_tool_both": await scenario(app, actors, model, kind="direct", fresh_each_turn=True,
                                       text="Xem lại những điều mình đã ghi rồi gợi ý hoạt động cuối tuần"),
        "handoff": await scenario(app, actors, model, kind="direct", fresh_each_turn=True,
                                  text="Mình muốn nói chuyện trực tiếp với Nhật ký"),
        "group_two_speakers": await scenario(app, actors, model, kind="group", text="@mọi người ơi giúp mình"),
    }
    settings.ai_smart_orchestration_enabled = False
    results["orchestration_flag_off"] = await scenario(app, actors, model, kind="direct",
                                                       text="Xem lại những điều mình đã ghi rồi gợi ý hoạt động cuối tuần")
    results["config"] = {"users": USERS, "turnsPerUser": TURNS, "callSeconds": CALL_SECONDS,
                         "pool": {"size": POOL[0], "overflow": POOL[1]}}
    app.state.database.engine = fixture_engine
    app.state.database.sessions = async_sessionmaker(fixture_engine, expire_on_commit=False)
    await engine.dispose()
    print(json.dumps(results, indent=2))
    if os.getenv("MOODPRINT_V3_LOAD_OUT"):
        await asyncio.to_thread(Path(os.environ["MOODPRINT_V3_LOAD_OUT"]).write_text,
                                json.dumps(results, indent=2), encoding="utf-8")
    assert results["single_agent"]["modelCallsPerTurn"] == 1.0
    assert results["orchestration_flag_off"]["modelCallsPerTurn"] == 1.0
    assert results["as_tool_both"]["modelCallsPerTurn"] == 5.0  # planner + 2 Điều phối + 2 specialists
    assert results["handoff"]["modelCallsPerTurn"] == 3.0  # planner + transfer + Nhật ký
    assert results["group_two_speakers"]["modelCallsPerTurn"] == 2.0  # @mọi người: no selector call
