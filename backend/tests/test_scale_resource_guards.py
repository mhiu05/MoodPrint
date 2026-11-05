import asyncio
import json
from uuid import uuid4

import pytest
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.core.config import Settings
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.core.streams import StreamSlots


def test_limiter_identity_memory_is_bounded_without_evicting_active_cooldowns(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.core.limits.time.monotonic", lambda: clock[0])
    limiter = AttemptLimiter(1, 60, max_keys=2)
    limiter.check("a")
    limiter.check("b")
    with pytest.raises(DomainError):
        limiter.check("c")
    assert len(limiter.attempts) == 2
    with pytest.raises(DomainError):
        limiter.check("a")
    clock[0] = 161
    limiter.check("c")
    assert len(limiter.attempts) == 1


def test_stream_limit_is_global_and_release_is_idempotent():
    slots = StreamSlots(6, total_limit=2)
    first, second, third = uuid4(), uuid4(), uuid4()
    release = slots.reserve(first)
    release_second = slots.reserve(second)
    with pytest.raises(DomainError):
        slots.reserve(third)
    release()
    release()
    release_third = slots.reserve(third)
    assert slots.open() == 2
    release_second()
    release_third()
    assert slots.open() == 0


@pytest.mark.postgres
async def test_pool_acquisition_wait_and_timeout_are_measured_without_credentials(database):
    from app.infrastructure.database.connection import Database

    settings = Settings(_env_file=None, database_url=database.url.render_as_string(hide_password=False),
                        database_pool_size=1, database_pool_overflow=0, database_pool_timeout=1,
                        database_pool_metrics_enabled=True)
    measured = Database(settings)
    try:
        async with measured.engine.connect():
            with pytest.raises(PoolTimeout):
                async with asyncio.timeout(3):
                    async with measured.engine.connect():
                        pytest.fail("Pool cap was bypassed")
        metrics = measured.pool_metrics()
        assert metrics["timeouts"] == 1 and metrics["p95_ms"] >= 900
        assert "postgres" not in json.dumps(metrics)
        assert measured.occupancy()[0] == 0
    finally:
        await measured.engine.dispose()
