from datetime import datetime

from moodprint_shared.contracts.base import FrozenDTO
from pydantic import AwareDatetime


class ArticleStatePut(FrozenDTO):
    bookmarked: bool = False
    read_at: AwareDatetime | None = None


class ArticleStateRead(ArticleStatePut):
    article_id: str
    created_at: datetime
    updated_at: datetime
