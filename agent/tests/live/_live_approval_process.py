"""Two-process approval round trip with the real model (L-AG-05). Never imported by the package.

``start`` asks the model to call a write tool, stops at the approval and saves the checkpoint;
``resume`` is a fresh interpreter with a fresh client that approves and finishes the run. Both
stages share the owner's budget ledger through the file system.
"""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from agents import RunContextWrapper, SQLiteSession
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.registry import ToolRegistry
from safevoice_shared.contracts.agent import AgentServices, AgentToolContext, ToolPolicy
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextBundle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _live import live_cfg, metered_client, open_ledger  # noqa: E402

STAGE = sys.argv[1]
DIRECTORY = Path(sys.argv[2])


async def save_test_process(ctx: RunContextWrapper[AgentToolContext], note: str) -> str:
    """Save a short synthetic note (writes only a marker file in a temp directory)."""
    (DIRECTORY / "executed.txt").write_text(note, encoding="utf-8")
    return "saved"


async def main() -> None:
    ledger = open_ledger()
    client, http = metered_client(ledger, f"live-approval-{STAGE}")
    registry = ToolRegistry()
    registry.register(save_test_process, ToolPolicy("save_test_process", "1", "write", True, 15, 1))
    ctx = AgentToolContext(
        auth=AuthContext(UUID(int=1), "test", "aal1", '{"private":"process-auth-canary"}'),
        request_id="live-approval",
        conversation_id=UUID(int=2),
        run_id=UUID(int=3),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace()),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )
    session = SQLiteSession("live-approval", db_path=DIRECTORY / "session.db")
    runtime = CompanionRuntime(live_cfg(ledger), registry, openai_client=client)
    try:
        if STAGE == "start":
            events = [
                e
                async for e in runtime.stream_turn(
                    ctx=ctx,
                    user_input=(
                        "Hãy gọi công cụ save_test_process với note là 'ghi chú thử nghiệm' "
                        "ngay bây giờ. Đây là bài kiểm tra kỹ thuật."
                    ),
                    session=session,
                )
            ]
            pending = runtime.pending_approvals(ctx.run_id)
            if pending:
                (DIRECTORY / "checkpoint.json").write_text(
                    pending[0].serialized_state, encoding="utf-8"
                )
        else:
            events = [
                e
                async for e in runtime.resume_after_approval(
                    ctx=ctx,
                    serialized_state=(DIRECTORY / "checkpoint.json").read_text(encoding="utf-8"),
                    approved=True,
                    session=session,
                )
            ]
    finally:
        await http.aclose()
    (DIRECTORY / f"{STAGE}.json").write_text(
        json.dumps([e.model_dump(mode="json", by_alias=True) for e in events], ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
