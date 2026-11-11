import base64
import json

from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.paging import Page
from sqlalchemy import text

from app.core.errors import ApiError
from app.core.uow import user_uow
from app.modules.knowledge_state.schemas import ArticleStatePut, ArticleStateRead


def dto(row):
    return ArticleStateRead.model_validate({k: row[k] for k in ArticleStateRead.model_fields})


class KnowledgeStateService:
    def __init__(self, engine):
        self.engine = engine

    async def list(self, auth: AuthContext, *, limit=50, cursor=None) -> Page[ArticleStateRead]:
        after = ""
        if cursor:
            try:
                raw = json.loads(
                    base64.b64decode(
                        cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
                    )
                )
                if (
                    raw.get("owner") != str(auth.user_id)
                    or raw.get("scope") != "article-states"
                    or not isinstance(raw.get("id"), str)
                ):
                    raise ValueError()
                after = raw["id"]
            except (ValueError, TypeError, AttributeError):
                raise ApiError(
                    "validation_failed", "Con trỏ phân trang không hợp lệ.", 422
                ) from None
        elif cursor is not None:
            raise ApiError("validation_failed", "Con trỏ phân trang không hợp lệ.", 422)
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.knowledge_article_states WHERE owner_id=:owner AND article_id>:after ORDER BY article_id LIMIT :limit"
                        ),
                        {"owner": auth.user_id, "after": after, "limit": limit + 1},
                    )
                ).mappings()
            )
        items = [dto(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            next_cursor = (
                base64.urlsafe_b64encode(
                    json.dumps(
                        {
                            "owner": str(auth.user_id),
                            "scope": "article-states",
                            "id": items[-1].article_id,
                        }
                    ).encode()
                )
                .decode()
                .rstrip("=")
            )
        return Page[ArticleStateRead](items=items, next_cursor=next_cursor)

    async def put(
        self, auth: AuthContext, article_id: str, data: ArticleStatePut
    ) -> ArticleStateRead:
        if not article_id or len(article_id) > 120:
            raise ApiError("validation_failed", "Mã bài viết không hợp lệ.", 422)
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text("""INSERT INTO app.knowledge_article_states(owner_id,article_id,bookmarked,read_at)
              VALUES(:owner,:article,:bookmarked,:read_at) ON CONFLICT(owner_id,article_id)
              DO UPDATE SET bookmarked=excluded.bookmarked,read_at=excluded.read_at RETURNING *"""),
                        {"owner": auth.user_id, "article": article_id, **data.model_dump()},
                    )
                )
                .mappings()
                .one()
            )
            return dto(row)
