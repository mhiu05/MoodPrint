"""Short owner-scoped queries for the foundation HTTP collections."""

from collections.abc import Sequence
from uuid import UUID

from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.conversations import ChatMessage
from moodprint_shared.contracts.errors import NotFound
from moodprint_shared.contracts.memory import Memory, MemoryCandidate
from moodprint_shared.contracts.paging import Page
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.paging import decode_cursor, encode_cursor
from app.core.uow import user_uow
from app.modules.conversations.schemas import ConversationRead


def _page[T: BaseModel](
    model: type[T],
    rows: Sequence[RowMapping],
    *,
    limit: int,
    scope: str,
    auth: AuthContext,
    at_column: str,
) -> Page[T]:
    visible = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = visible[-1]
        next_cursor = encode_cursor(
            scope=scope, owner=auth.user_id, at=last[at_column], id=last["id"]
        )
    return Page[T](
        items=[
            model.model_validate({name: row[name] for name in model.model_fields if name in row})
            for row in visible
        ],
        next_cursor=next_cursor,
    )


class FoundationPages:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def conversations(
        self, auth: AuthContext, *, limit: int, cursor: str | None
    ) -> Page[ConversationRead]:
        scope = "conversations"
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        params = {"owner": auth.user_id, "limit": limit + 1}
        predicate = ""
        if position:
            params["id"] = position.id
            if position.at is None:
                predicate = "AND last_message_at IS NULL AND id>:id"
            else:
                params["at"] = position.at
                predicate = "AND (last_message_at<:at OR (last_message_at=:at AND id>:id) OR last_message_at IS NULL)"
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.conversations WHERE owner_id=:owner {predicate} ORDER BY last_message_at DESC NULLS LAST,id ASC LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        return _page(
            ConversationRead, rows, limit=limit, scope=scope, auth=auth, at_column="last_message_at"
        )

    async def messages(
        self, auth: AuthContext, conversation_id: UUID, *, limit: int, cursor: str | None
    ) -> Page[ChatMessage]:
        scope = f"messages:{conversation_id}"
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        params = {"owner": auth.user_id, "conversation": conversation_id, "limit": limit + 1}
        predicate = ""
        if position:
            params.update(at=position.at, id=position.id)
            predicate = "AND (created_at,id)>(:at,:id)"
        async with user_uow(self.engine, auth) as uow:
            if (
                await uow.session.scalar(
                    text(
                        "SELECT id FROM app.conversations WHERE id=:conversation AND owner_id=:owner"
                    ),
                    params,
                )
                is None
            ):
                raise NotFound()
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.messages WHERE owner_id=:owner AND conversation_id=:conversation {predicate} ORDER BY created_at ASC,id ASC LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        return _page(ChatMessage, rows, limit=limit, scope=scope, auth=auth, at_column="created_at")

    async def memories(self, auth: AuthContext, *, limit: int, cursor: str | None) -> Page[Memory]:
        scope = "memories"
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        params = {"owner": auth.user_id, "limit": limit + 1}
        predicate = ""
        if position:
            params.update(at=position.at, id=position.id)
            predicate = "AND (updated_at<:at OR (updated_at=:at AND id>:id))"
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.user_memories WHERE owner_id=:owner AND status='active' {predicate} ORDER BY updated_at DESC,id ASC LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        return _page(Memory, rows, limit=limit, scope=scope, auth=auth, at_column="updated_at")

    async def candidates(
        self, auth: AuthContext, *, limit: int, cursor: str | None
    ) -> Page[MemoryCandidate]:
        scope = "memory-candidates"
        position = decode_cursor(cursor, scope=scope, owner=auth.user_id)
        params = {"owner": auth.user_id, "limit": limit + 1}
        predicate = ""
        if position:
            params.update(at=position.at, id=position.id)
            predicate = "AND (created_at,id)>(:at,:id)"
        async with user_uow(self.engine, auth) as uow:
            rows = list(
                (
                    await uow.session.execute(
                        text(
                            f"SELECT * FROM app.memory_candidates WHERE owner_id=:owner AND status='pending' AND expires_at>now() {predicate} ORDER BY created_at ASC,id ASC LIMIT :limit"
                        ),
                        params,
                    )
                ).mappings()
            )
        return _page(
            MemoryCandidate, rows, limit=limit, scope=scope, auth=auth, at_column="created_at"
        )
