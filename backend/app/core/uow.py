"""Every request transaction derives claims exclusively from verified AuthContext."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from safevoice_shared.contracts.auth import AuthContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.errors import ApiError

_deletion_scope: ContextVar[tuple[UUID, asyncio.Task | None] | None] = ContextVar(
    "account_deletion_scope", default=None
)


@contextmanager
def account_deletion_scope(auth: AuthContext) -> Iterator[None]:
    """Internal cleanup access, limited to one owner and the calling asyncio task.

    ContextVars copy into child tasks; task identity prevents that copy from granting
    background work the ability to mutate an account while it is being deleted.
    """
    token = _deletion_scope.set((auth.user_id, asyncio.current_task()))
    try:
        yield
    finally:
        _deletion_scope.reset(token)


@dataclass(slots=True)
class UnitOfWork:
    session: AsyncSession


@asynccontextmanager
async def user_uow(engine: AsyncEngine, auth: AuthContext) -> AsyncIterator[UnitOfWork]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(text("SET LOCAL ROLE authenticated"))
            await session.execute(
                text("SELECT set_config('request.jwt.claims', :claims, true)"),
                {"claims": auth.claims_json},
            )
            # Every user transaction joins this lock, including the first deletion
            # snapshot. Release it on commit before Storage/Auth network calls.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "account:" + str(auth.user_id)},
            )
            deletion_started = await session.scalar(
                text("SELECT deletion_started_at FROM app.profiles WHERE user_id=:owner"),
                {"owner": auth.user_id},
            )
            if deletion_started is not None and _deletion_scope.get() != (
                auth.user_id,
                asyncio.current_task(),
            ):
                raise ApiError("account_deleting", "Tài khoản đang được xóa.", 409)
            yield UnitOfWork(session)
