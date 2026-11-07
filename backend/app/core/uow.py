"""Every request transaction derives claims exclusively from verified AuthContext."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from moodprint_shared.contracts.auth import AuthContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


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
            yield UnitOfWork(session)
