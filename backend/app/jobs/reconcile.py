import asyncio

from sqlalchemy import text


async def reconcile_once(engine, stale_seconds: int = 180) -> int:
    # No SET ROLE or user content access here: EXECUTE on a single narrow function.
    async with engine.begin() as connection:
        return await connection.scalar(
            text("SELECT app_private.reconcile_stale_runs(make_interval(secs=>:seconds))"),
            {"seconds": stale_seconds},
        )


async def reconcile_loop(engine, interval_s: float = 30, stale_seconds: int = 180):
    while True:
        try:
            await reconcile_once(engine, stale_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Readiness exposes DB failures; do not print driver exceptions/credentials/content.
            pass
        await asyncio.sleep(interval_s)


async def main():
    from moodprint_shared.config import AppConfig
    from moodprint_shared.env import get_settings

    from app.core.db import create_engine

    engine = create_engine(get_settings(), AppConfig())
    try:
        print(f"Interrupted stale runs: {await reconcile_once(engine)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
