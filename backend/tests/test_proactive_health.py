"""Worker health requires successful readiness and ticks, including an idle tick."""

import asyncio
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.jobs import proactive as worker


@pytest.mark.parametrize("fail_first", [True, False])
async def test_failed_ticks_cannot_create_or_refresh_worker_health(tmp_path, monkeypatch, fail_first):
    import app.ai.runtime
    import app.infrastructure.database.connection

    heartbeat = tmp_path / "beat"
    stop = asyncio.Event()
    settings = SimpleNamespace(proactive_worker_enabled=True, proactive_worker_concurrency=1)
    database = SimpleNamespace(engine=None)
    runtime = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(app.infrastructure.database.connection, "Database", lambda _: database)
    monkeypatch.setattr(app.ai.runtime, "AiRuntime", lambda *_: runtime)
    monkeypatch.setattr(worker, "wait_ready", AsyncMock(return_value=True))
    calls = 0

    async def tick(_):
        nonlocal calls
        calls += 1
        if not fail_first and calls == 1:
            return {"claimed": 1}  # successful pass drains again immediately
        if heartbeat.exists():
            stale = time.time() - 300
            os.utime(heartbeat, (stale, stale))
        stop.set()
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(worker, "proactive_tick", tick)
    await worker.serve(settings, stop=stop, heartbeat=heartbeat)
    assert not worker.healthy(heartbeat)
    if fail_first:
        assert not heartbeat.exists()
    runtime.close.assert_awaited_once()


async def test_successful_disabled_tick_keeps_idle_worker_healthy(tmp_path, monkeypatch):
    import app.ai.runtime
    import app.infrastructure.database.connection

    heartbeat = tmp_path / "beat"
    stop = asyncio.Event()
    settings = SimpleNamespace(proactive_worker_enabled=False, proactive_worker_concurrency=1)
    database = SimpleNamespace(engine=None)
    runtime = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(app.infrastructure.database.connection, "Database", lambda _: database)
    monkeypatch.setattr(app.ai.runtime, "AiRuntime", lambda *_: runtime)
    monkeypatch.setattr(worker, "wait_ready", AsyncMock(return_value=True))

    async def tick(_):
        stop.set()
        return {"enabled": False}

    monkeypatch.setattr(worker, "proactive_tick", tick)
    await worker.serve(settings, stop=stop, heartbeat=heartbeat)
    assert worker.healthy(heartbeat)
