"""Small owner-only journal excerpts for Nhịp; never media or legacy mood notes."""

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from sqlalchemy import select

from app.contracts import DTO
from app.core.errors import DomainError


class JournalSearchInput(DTO):
    query: str = Field(default="", max_length=80)
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=5, ge=1, le=5)

    @model_validator(mode="after")
    def bounded_range(self):
        if (
            self.from_date
            and self.to_date
            and not timedelta(0) <= self.to_date - self.from_date <= timedelta(days=89)
        ):
            raise ValueError("Select between one and 90 consecutive days")
        return self


async def search_for_ai(db, user, *, query="", from_date=None, to_date=None, limit=5):
    """The caller owns live actor/AI checks; the locked User owns every query filter."""
    from app.modules.journal.models import JournalEntry

    args = JournalSearchInput(query=query, from_date=from_date, to_date=to_date, limit=limit)
    today = datetime.now(ZoneInfo(user.timezone)).date()
    start, end = args.from_date or today - timedelta(days=89), args.to_date or today
    if start > end or end > today or start < today - timedelta(days=89):
        raise DomainError(422, "JOURNAL_SCOPE_EXPIRED", "Chọn khoảng ngày trong 90 ngày gần đây.")
    statement = select(JournalEntry).where(
        JournalEntry.user_id == user.id,
        JournalEntry.status == "saved",
        JournalEntry.local_date >= start,
        JournalEntry.local_date <= end,
    )
    query = args.query.strip()
    if query:
        # Literal substring: model-controlled % and _ never become wildcards.
        statement = statement.where(JournalEntry.text.icontains(query, autoescape=True))
    rows = (
        await db.scalars(
            statement.order_by(
                JournalEntry.local_date.desc(),
                JournalEntry.created_at.desc(),
                JournalEntry.id.desc(),
            ).limit(args.limit + 1)
        )
    ).all()
    entries: list[dict[str, Any]] = []
    for row in rows[: args.limit]:
        position = row.text.lower().find(query.lower()) if query else 0
        offset = max(0, position - 300)
        snippet = row.text[offset : offset + 1000]
        candidate = {
            "id": str(row.id),
            "version": row.version,
            "localDate": str(row.local_date),
            "mood": row.mood,
            "emotions": [str(item)[:48] for item in row.emotions[:12]],
            "factors": [str(item)[:48] for item in row.factors[:12]],
            "snippet": snippet,
            "snippetTruncated": offset > 0 or offset + len(snippet) < len(row.text),
        }
        if len(json.dumps(entries + [candidate], ensure_ascii=False).encode()) > 24_000:
            break
        entries.append(candidate)
    return {
        "entries": entries,
        "coverage": {
            "from": str(start),
            "to": str(end),
            "returnedCount": len(entries),
            "hasMore": len(rows) > len(entries),
            "limit": args.limit,
            "completeHistory": False,
        },
    }
