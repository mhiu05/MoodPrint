from uuid import uuid4

from agents import SQLiteSession
from moodprint_agent.memory.session import make_compaction_session, make_session, repair_session
from moodprint_shared.config import AppConfig
from sqlalchemy.ext.asyncio import create_async_engine


async def test_factory_uses_private_schema_utf8_and_no_ddl() -> None:
    engine = create_async_engine("postgresql+asyncpg://test:test@127.0.0.1/test")
    try:
        session = make_session(uuid4(), engine, AppConfig())
        assert session.engine.get_execution_options()["schema_translate_map"] == {
            None: "agent_store"
        }
        assert session._create_tables is False
        assert "bạn thân" in await session._serialize_item({"role": "user", "content": "bạn thân"})
        assert list(session._sessions.c.keys()) == ["session_id", "created_at", "updated_at"]
        assert list(session._messages.c.keys()) == [
            "id",
            "session_id",
            "message_data",
            "created_at",
        ]
    finally:
        await engine.dispose()


async def test_repair_removes_only_unfinished_tool_suffix() -> None:
    session = SQLiteSession("repair")
    await session.add_items(
        [
            {"role": "user", "content": "Xin chào"},
            {"type": "function_call", "name": "clock", "call_id": "old", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "old", "output": "ok"},
            {"type": "function_call", "name": "clock", "call_id": "broken", "arguments": "{}"},
        ]
    )
    assert await repair_session(session) == 1
    assert len(await session.get_items()) == 3
    assert await repair_session(session) == 0


async def test_compaction_factory_disables_default_trigger_without_network() -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key="synthetic-key", base_url="http://127.0.0.1:9", max_retries=0)
    try:
        inner = SQLiteSession("compaction-test")
        await inner.add_items([{"role": "user", "content": f"synthetic {i}"} for i in range(20)])
        wrapper = make_compaction_session(uuid4(), inner, AppConfig(), client=client)
        await wrapper.run_compaction({"store": False})
        assert len(await wrapper.get_items()) == 20
    finally:
        await client.close()
