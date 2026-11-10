"""Keep integration tests from silently replacing the published corpus of the kb database."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from moodprint_agent.knowledge.ingest.runtime import engine_for, rollback_version
from sqlalchemy import text

from .kb_env import load_test_env


async def _published() -> str | None:
    engine = engine_for("test-env")
    try:
        async with engine.connect() as conn:
            return (
                await conn.execute(
                    text("select version from knowledge.corpus_versions where status = 'published'")
                )
            ).scalar_one_or_none()
    finally:
        await engine.dispose()


async def _restore(version: str) -> None:
    engine = engine_for("test-env")
    try:
        await rollback_version(engine, version)
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def keep_published_corpus(request: pytest.FixtureRequest) -> Iterator[None]:
    """Integration tests seed and publish synthetic corpora; put the live one back afterwards."""
    if request.node.get_closest_marker("integration") is None:
        yield
        return
    load_test_env()
    before = asyncio.run(_published())
    yield
    if before is not None and asyncio.run(_published()) != before:
        asyncio.run(_restore(before))
