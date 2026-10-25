"""Content-free daily matching counters per scorer version (C-08). No user identifiers."""

from datetime import date
from typing import Literal

from sqlalchemy.dialects.postgresql import insert

from app.modules.social.models import MatchingStatsDaily

Counter = Literal["impressions", "requests", "accepts"]


async def bump(db, field: Counter, scoring_version: str, day: date, amount: int = 1) -> None:
    """Add to one counter inside the caller's transaction (so a rollback undoes it)."""
    if amount <= 0:
        return
    statement = insert(MatchingStatsDaily).values(
        day=day, scoring_version=scoring_version, **{field: amount}
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[MatchingStatsDaily.day, MatchingStatsDaily.scoring_version],
            set_={field: getattr(MatchingStatsDaily, field) + getattr(statement.excluded, field)},
        )
    )
