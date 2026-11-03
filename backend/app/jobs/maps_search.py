"""Dedicated Maps poll/abort/reconcile worker; never starts an actor or model."""

import argparse
import asyncio
import logging
import signal
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from app.ai.search.maps_jobs import advance_one, provider_client

HEARTBEAT = Path(tempfile.gettempdir()) / "moodprint-maps.heartbeat"


def healthy(path=HEARTBEAT):
    try:
        return time.time() - path.stat().st_mtime < 120
    except OSError:
        return False


async def serve(settings, stop):
    from app.infrastructure.database.connection import Database
    from app.jobs.proactive import wait_ready

    database = Database(settings)
    HEARTBEAT.unlink(missing_ok=True)
    client = None
    try:
        if not await wait_ready(database, stop):
            return
        # Worker keeps cleaning pending jobs even with AI_MAPS_SEARCH_ENABLED=false.
        provider = None
        if settings.apify_api_token.get_secret_value() and settings.apify_maps_actor_build:
            client, provider = provider_client(settings)
        while not stop.is_set():
            try:
                if provider is not None:
                    await advance_one(database, provider)
                else:
                    from sqlalchemy import select

                    from app.ai.search.models import AiMapsSearch
                    async with database.require()() as db:
                        pending = await db.scalar(select(AiMapsSearch.id).where(AiMapsSearch.cleanup_done.is_(False)).limit(1))
                    if pending:
                        raise RuntimeError("Maps cleanup needs provider config")
            except Exception as error:
                logging.getLogger("moodprint").error("metric=maps_tick_error error_type=%s", type(error).__name__)
            else:
                HEARTBEAT.touch()
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), 1)
    finally:
        if client:
            await client.aclose()
        if database.engine:
            await database.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if args.health:
        return 0 if healthy() else 1
    from app.core.config import Settings
    settings = Settings()
    settings.database_pool_size, settings.database_pool_overflow = 1, 0
    async def run():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
        await serve(settings, stop)
    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
