from pydantic import Field

from .base import FrozenDTO


class Page[T](FrozenDTO):
    items: list[T]
    next_cursor: str | None = None


class PageQuery(FrozenDTO):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None
