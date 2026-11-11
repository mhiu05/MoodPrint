from datetime import datetime

from pydantic import AwareDatetime
from safevoice_shared.contracts.base import FrozenDTO


class ArticleStatePut(FrozenDTO):
    bookmarked: bool = False
    read_at: AwareDatetime | None = None


class ArticleStateRead(ArticleStatePut):
    article_id: str
    created_at: datetime
    updated_at: datetime
