"""Load-test stand-in for the `proactive` Compose service (synthetic model, local *_test DB only).

Runs the real proactive_tick loop in its own process with the worker pool (2+0 by default),
until the queue is drained, and prints content-free JSON stats on stdout.
"""
# ruff: noqa: E402

import asyncio
import json
import os
import sys
import time

from sqlalchemy.engine import make_url

url = os.environ.get("TEST_DATABASE_URL", "")
target = make_url(url) if url else None
if not target or target.host not in ("127.0.0.1", "localhost") or not target.database.endswith("_test"):
    raise RuntimeError("Load worker requires a disposable local *_test database")
os.environ.update({"APP_ENV": "test", "OPENAI_API_KEY": "", "AI_ENABLED": "false", "VOYAGE_API_KEY": ""})

from app.core.config import Settings
from app.infrastructure.database.connection import Database
from app.jobs.proactive import proactive_tick
from tests.fakes import ScriptedModel, message_output


class SlowCheckInModel(ScriptedModel):
    """Answers every check-in after a fixed provider latency."""

    def __init__(self, delay: float):
        super().__init__([])
        self.delay = delay

    async def stream_response(self, *args, **kwargs):
        content = args[1][0]["content"]
        data = json.loads(content.split(": ", 1)[1])
        reply: dict = {"messages": [{"text": "Một lời chào nhỏ cho hôm nay.", "cards": []}]}
        if data["companion"] == "nhip":
            reply["source_entry_ids"] = []
        if data["companion"] == "rure":
            reply["challenge_kind"] = next(k for k in ("observation", "riddle", "drawing", "word_play")
                                           if k not in data.get("avoidChallengeKinds", []))
        self.responses = [[message_output(json.dumps(reply, ensure_ascii=False))]]
        await asyncio.sleep(self.delay)
        async for event in super().stream_response(*args, **kwargs):
            yield event


async def main() -> None:
    from app.ai.runtime import AiRuntime

    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    settings = Settings(
        _env_file=None, app_env="test", database_url=url,
        database_pool_size=int(os.environ.get("DATABASE_POOL_SIZE", "2")),
        database_pool_overflow=int(os.environ.get("DATABASE_POOL_OVERFLOW", "0")),
        proactive_enabled=True, proactive_worker_enabled=True,
        proactive_worker_concurrency=concurrency, proactive_daily_cap_per_user=6,
        ai_global_concurrency=int(os.environ.get("AI_GLOBAL_CONCURRENCY", "50")),
    )
    database = Database(settings)
    runtime = AiRuntime(settings, database)
    runtime.model_override = SlowCheckInModel(delay)
    peak = {"checked_out": 0}
    stop = asyncio.Event()

    async def sample():
        while not stop.is_set():
            checked, _overflow = database.occupancy()
            peak["checked_out"] = max(peak["checked_out"], checked or 0)
            await asyncio.sleep(0.02)

    sampler = asyncio.create_task(sample())
    started = time.monotonic()
    ticks = claimed = idle = 0
    while idle < 3 and time.monotonic() - started < 1800:
        result = await proactive_tick(runtime)
        ticks += 1
        claimed += result.get("claimed", 0)
        idle = idle + 1 if not result.get("claimed") else 0
        if not result.get("claimed"):
            await asyncio.sleep(0.5)
    stop.set()
    await sampler
    await runtime.close()
    await database.engine.dispose()
    print(json.dumps({"ticks": ticks, "claimed": claimed, "seconds": round(time.monotonic() - started, 2),
                      "pool_peak_checked_out": peak["checked_out"], "concurrency": concurrency}))


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
