"""Local session-read load probe.

Refuses any non-loopback database. This does not exercise the production
session query; it measures pool acquisition and a single SELECT 1 under the
recommended 5+2 budget.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import statistics
import sys
import time
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _require_loopback(url: str) -> None:
    host = (urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1)).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing to load-test a non-loopback database")


async def _once(engine, results: list[float], errors: list[str]) -> None:
    started = time.perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
        results.append((time.perf_counter() - started) * 1000)
    except Exception as error:
        errors.append(type(error).__name__)


async def run(url: str, users: int, requests: int) -> dict:
    engine = create_async_engine(
        url,
        pool_size=5,
        max_overflow=2,
        pool_timeout=10,
        pool_pre_ping=True,
    )
    results: list[float] = []
    errors: list[str] = []
    pending = requests

    async def worker() -> None:
        nonlocal pending
        while True:
            if pending <= 0:
                return
            pending -= 1
            await _once(engine, results, errors)

    started = time.perf_counter()
    await asyncio.gather(*[worker() for _ in range(users)])
    elapsed = time.perf_counter() - started
    await engine.dispose()
    ordered = sorted(results)

    def percentile(rank: float) -> float | None:
        if not ordered:
            return None
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * rank)))
        return round(ordered[index], 2)

    return {
        "users": users,
        "requests": requests,
        "ok": len(results),
        "errors": len(errors),
        "error_types": sorted(set(errors)),
        "elapsed_s": round(elapsed, 3),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "mean_ms": round(statistics.fmean(results), 2) if results else None,
        "pool": "5+2",
        "query": "select 1",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--requests", type=int, default=200)
    args = parser.parse_args()
    url = args.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    _require_loopback(url)
    runner = asyncio.run
    if sys.platform == "win32":
        def runner(coro):
            return asyncio.run(coro, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    print(json.dumps(runner(run(url, args.users, args.requests)), ensure_ascii=False))


if __name__ == "__main__":
    main()
