"""S-02: real local PostgreSQL, migration-created tables, and engine restart."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from safevoice_agent.memory.session import make_session
from safevoice_shared.config import AppConfig
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def local_database_url() -> str:
    fixture = Path(__file__).resolve().parents[3] / ".local" / "test.env"
    values = dotenv_values(fixture) if fixture.exists() else {}
    url = os.environ.get("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required for S-02; bootstrap the local stack first")
    if make_url(url).host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("S-02 requires a loopback database")
    return url


async def test_session_survives_engine_restart_and_stores_vietnamese_as_utf8() -> None:
    url, conversation_id, cfg = local_database_url(), uuid4(), AppConfig()
    first_engine = create_async_engine(url)
    first = make_session(conversation_id, first_engine, cfg)
    item = {"role": "user", "content": "Mình muốn nói chuyện với bạn thân."}
    await first.add_items([item])
    await first_engine.dispose()

    second_engine = create_async_engine(url)
    second = make_session(conversation_id, second_engine, cfg)
    try:
        assert await second.get_items() == [item]
        async with second_engine.connect() as connection:
            stored = (
                await connection.execute(
                    text(
                        "select message_data from agent_store.agent_messages where session_id = :id"
                    ),
                    {"id": str(conversation_id)},
                )
            ).scalar_one()
            assert "bạn thân" in stored
            assert "\\u1" not in stored
        assert second.engine.get_execution_options()["schema_translate_map"][None] == "agent_store"
    finally:
        await second.clear_session()
        async with second_engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM agent_store.agent_sessions WHERE session_id=:id"),
                {"id": str(conversation_id)},
            )
        await second_engine.dispose()
