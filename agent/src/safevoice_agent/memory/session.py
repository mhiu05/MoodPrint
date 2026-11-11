"""SDK session factory; ownership is checked by ConversationService first."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from agents import Session, SessionSettings
from agents.extensions.memory import SQLAlchemySession
from agents.memory import OpenAIResponsesCompactionSession
from openai import AsyncOpenAI
from safevoice_shared.config import AppConfig
from sqlalchemy.ext.asyncio import AsyncEngine


def make_session(conversation_id: UUID, engine: AsyncEngine, cfg: AppConfig) -> SQLAlchemySession:
    store_engine = engine.execution_options(schema_translate_map={None: "agent_store"})
    return SQLAlchemySession(
        str(conversation_id),
        engine=store_engine,
        create_tables=False,
        ensure_ascii=False,
        session_settings=SessionSettings(limit=cfg.agent.session_item_limit),
    )


def disabled_compaction_policy(context: dict[str, Any]) -> bool:
    """Phase 0 never sends a compaction request."""
    return False


def make_compaction_session(
    conversation_id: UUID,
    underlying_session: Session,
    cfg: AppConfig,
    *,
    client: AsyncOpenAI,
    policy: Callable[[dict[str, Any]], bool] = disabled_compaction_policy,
) -> OpenAIResponsesCompactionSession:
    return OpenAIResponsesCompactionSession(
        session_id=str(conversation_id),
        underlying_session=underlying_session,
        client=client,
        model=cfg.agent.compaction_model,
        compaction_mode="input",
        should_trigger_compaction=policy,
    )


async def repair_session(session: Session) -> int:
    """Remove an unfinished tool-call suffix before retrying an interrupted turn."""
    items = await session.get_items()
    pending: dict[str, int] = {}
    for index, item in enumerate(items):
        kind = item.get("type")
        call_id = item.get("call_id")
        if not isinstance(call_id, str):
            continue
        if kind == "function_call":
            pending[call_id] = index
        elif kind == "function_call_output":
            pending.pop(call_id, None)
    if not pending:
        return 0
    count = len(items) - min(pending.values())
    for _ in range(count):
        await session.pop_item()
    return count
