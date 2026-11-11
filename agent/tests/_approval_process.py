"""Two-process approval experiment; never imported by the production package."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from agents import RunContextWrapper, SQLiteSession
from agents.testing import ScriptedModel, assistant_message, function_call
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.registry import ToolRegistry
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.agent import AgentServices, AgentToolContext, ToolPolicy
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextBundle

STAGE = sys.argv[1]
DIRECTORY = Path(sys.argv[2])


async def save_test_process(ctx: RunContextWrapper[AgentToolContext], note: str) -> str:
    """Save a synthetic note in a test-only marker file."""
    (DIRECTORY / "executed.txt").write_text(note, encoding="utf-8")
    return "saved"


async def main() -> None:
    registry = ToolRegistry()
    registry.register(save_test_process, ToolPolicy("save_test_process", "1", "write", True, 15, 1))
    ctx = AgentToolContext(
        auth=AuthContext(UUID(int=1), "test", "aal1", '{"private":"process-auth-canary"}'),
        request_id="process-test",
        conversation_id=UUID(int=2),
        run_id=UUID(int=3),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace()),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )
    session = SQLiteSession("process-test", db_path=DIRECTORY / "session.db")
    if STAGE == "start":
        runtime = CompanionRuntime(
            AppConfig(),
            registry,
            model=ScriptedModel(
                [
                    [
                        function_call(
                            "save_test_process",
                            {"note": "synthetic persisted note"},
                            call_id="process-write",
                        )
                    ],
                ]
            ),
        )
        events = [
            e async for e in runtime.stream_turn(ctx=ctx, user_input="Lưu ghi chú", session=session)
        ]
        (DIRECTORY / "checkpoint.json").write_text(
            runtime.pending_approvals(ctx.run_id)[0].serialized_state, encoding="utf-8"
        )
    else:
        runtime = CompanionRuntime(
            AppConfig(), registry, model=ScriptedModel([[assistant_message("Đã lưu.")]])
        )
        events = [
            e
            async for e in runtime.resume_after_approval(
                ctx=ctx,
                serialized_state=(DIRECTORY / "checkpoint.json").read_text(encoding="utf-8"),
                approved=True,
                session=session,
            )
        ]
    (DIRECTORY / f"{STAGE}.json").write_text(
        json.dumps([e.model_dump(mode="json", by_alias=True) for e in events], ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
