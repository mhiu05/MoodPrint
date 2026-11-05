"""Small owner-only journal excerpts for Nhịp; never media or legacy mood notes."""

from datetime import date, timedelta

from pydantic import Field, model_validator

from app.contracts import DTO


class JournalSearchInput(DTO):
    query: str = Field(default="", max_length=80)
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=6, ge=1, le=8)

    @model_validator(mode="after")
    def bounded_range(self):
        if (
            self.from_date
            and self.to_date
            and not timedelta(0) <= self.to_date - self.from_date <= timedelta(days=89)
        ):
            raise ValueError("Select between one and 90 consecutive days")
        return self


async def search_for_ai(db, user, *, query="", from_date=None, to_date=None, limit=6):
    """Compatibility wrapper: keyword/recent ranking without provider I/O."""
    from app.modules.journal.retrieval import hybrid_search

    args = JournalSearchInput(query=query, from_date=from_date, to_date=to_date, limit=limit)
    return await hybrid_search(db, user, args, query_vector=None, settings=None, reason="disabled")
