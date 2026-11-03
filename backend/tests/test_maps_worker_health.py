"""Local process/DB liveness checks; no live provider, credentials or database."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.jobs import maps_search


def test_heartbeat_requires_a_fresh_marker(tmp_path, monkeypatch):
    marker = tmp_path / "heartbeat"
    assert not maps_search.healthy(marker)
    marker.touch()
    at = marker.stat().st_mtime
    monkeypatch.setattr(maps_search.time, "time", lambda: at + 119)
    assert maps_search.healthy(marker)
    monkeypatch.setattr(maps_search.time, "time", lambda: at + 120)
    assert not maps_search.healthy(marker)


@pytest.mark.parametrize("failed_tick", [False, True])
async def test_worker_clears_stale_marker_and_only_marks_successful_db_ticks(tmp_path, monkeypatch, failed_tick):
    from app.infrastructure.database import connection
    from app.jobs import proactive

    marker = tmp_path / "heartbeat"
    marker.touch()
    stop = asyncio.Event()
    database = SimpleNamespace(engine=SimpleNamespace(dispose=AsyncMock()))
    client = SimpleNamespace(aclose=AsyncMock())
    provider = object()
    monkeypatch.setattr(maps_search, "HEARTBEAT", marker)
    monkeypatch.setattr(connection, "Database", lambda settings: database)
    async def ready(db, event):
        assert not marker.exists(), "a restart cannot inherit the old process heartbeat"
        return True
    monkeypatch.setattr(proactive, "wait_ready", ready)
    monkeypatch.setattr(maps_search, "provider_client", lambda settings: (client, provider))
    async def tick(db, adapter):
        assert db is database and adapter is provider
        stop.set()
        if failed_tick:
            raise OSError("synthetic DB failure")
        return False  # An empty queue is healthy, even with admission switched off.
    monkeypatch.setattr(maps_search, "advance_one", tick)
    await maps_search.serve(SimpleNamespace(apify_api_token=SecretStr("synthetic"), apify_maps_actor_build="test123", ai_maps_search_enabled=False), stop)
    assert marker.exists() is not failed_tick
    client.aclose.assert_awaited_once()
    database.engine.dispose.assert_awaited_once()


async def test_worker_never_marks_health_when_schema_is_not_ready(tmp_path, monkeypatch):
    from app.infrastructure.database import connection
    from app.jobs import proactive

    marker = tmp_path / "heartbeat"
    marker.touch()
    database = SimpleNamespace(engine=SimpleNamespace(dispose=AsyncMock()))
    monkeypatch.setattr(maps_search, "HEARTBEAT", marker)
    monkeypatch.setattr(connection, "Database", lambda settings: database)
    monkeypatch.setattr(proactive, "wait_ready", AsyncMock(return_value=False))
    await maps_search.serve(SimpleNamespace(), asyncio.Event())
    assert not marker.exists()
    database.engine.dispose.assert_awaited_once()
