"""Read-only weekly beta metrics from matching_stats_daily (05 section 13).

    cd backend && uv run --locked python ../scripts/report_beta_metrics.py \
        --database-url-env TEST_DATABASE_URL --days 7

Aggregates only; cells below 5 are suppressed. Refuses hosted databases unless the
operator passes --approved (approval is required per session; see 11 section 4).
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

MIN_CELL = 5
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def suppress(value: int):
    return value if value >= MIN_CELL else f"<{MIN_CELL}"


def rate(numerator: int, denominator: int):
    if numerator < MIN_CELL or denominator < MIN_CELL:
        return None
    return round(numerator / denominator, 3)


def summarize(rows) -> list[dict]:
    totals: dict[str, dict[str, int]] = {}
    for _day, version, impressions, requests, accepts in rows:
        bucket = totals.setdefault(version, {"impressions": 0, "requests": 0, "accepts": 0})
        bucket["impressions"] += impressions
        bucket["requests"] += requests
        bucket["accepts"] += accepts
    return [
        {
            "scoringVersion": version,
            "impressions": suppress(values["impressions"]),
            "requests": suppress(values["requests"]),
            "accepts": suppress(values["accepts"]),
            "requestRate": rate(values["requests"], values["impressions"]),
            "acceptRate": rate(values["accepts"], values["requests"]),
        }
        for version, values in sorted(totals.items())
    ]


def check_target(url: str, approved: bool) -> str:
    target = make_url(url)
    if target.host not in LOCAL_HOSTS and not approved:
        raise SystemExit(
            "Refusing a non-local database without --approved (hosted reads need approval)"
        )
    return url


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-env", default="DATABASE_URL")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    url = check_target(os.environ.get(args.database_url_env, ""), args.approved)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = (
                await connection.execute(
                    text(
                        "select day, scoring_version, impressions, requests, accepts "
                        "from moodprint.matching_stats_daily where day >= :since"
                    ),
                    {"since": date.today() - timedelta(days=args.days)},
                )
            ).all()
    finally:
        await engine.dispose()
    print(json.dumps({"days": args.days, "byScorer": summarize(rows)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
