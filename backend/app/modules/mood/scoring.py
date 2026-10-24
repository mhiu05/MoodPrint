"""Pure parity oracle for the frontend's seven-day mood summary."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any


def demo_date(clock_ms: int) -> str:
    """Keep the original fixed UTC+7 day boundary for millisecond timestamps."""
    return (
        (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=clock_ms, hours=7))
        .date()
        .isoformat()
    )


def mood_summary(entries: Sequence[Mapping[str, Any]], clock_ms: int) -> dict[str, Any]:
    """Summarize distinct days; missing days never contribute a zero value."""
    end = datetime.fromisoformat(demo_date(clock_ms)).date()
    buckets = []
    points = []
    for offset in range(6, -1, -1):
        day = (end - timedelta(days=offset)).isoformat()
        items = [entry for entry in entries if entry["date"] == day]
        entry = max(items, key=lambda item: (item["time"], item["id"]), default=None)
        buckets.append({"date": day, "entry": entry})
        if entry is not None:
            points.append(entry["value"])
    return {
        "buckets": buckets,
        "count": len(points),
        "mean": sum(points) / len(points) if points else None,
        "min": min(points) if points else None,
        "max": max(points) if points else None,
    }
