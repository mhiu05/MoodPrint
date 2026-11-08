"""Live compatibility smoke for ``gpt-6-luna`` + openai-agents 0.24.0 (P3-00, L-AG-01…06).

STATUS: NOT EXECUTED. The bodies below have never run against the real API because no
owner-approved ``.local/eval-budget.json`` and no ``OPENAI_API_KEY`` were available. They refuse to
run without both (exit code 3). L-AG-04/05/06 are intentionally unimplemented; do not count them
as passing.

Every request passes through ``GuardedTransport``: it must be to the Responses endpoint, use the
approved model, send ``store=False`` and an output cap, and fit the owner's call/token/USD caps.
"""

import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from evals.budget import (
    DEFAULT_BUDGET_PATH,
    BudgetError,
    BudgetLedger,
    GuardedTransport,
    load_budget,
)
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.context import CompanionToolContext
from moodprint_agent.tools.factory import build_registry
from moodprint_agent.tools.registry import diagnostic_registry
from moodprint_shared.config import OPENAI_MODEL, AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextBundle
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
from openai import AsyncOpenAI

pytestmark = pytest.mark.live_agent
SCOPE = "phase3-live-compat"


def _api_key() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    env_live = Path(".env.live")
    if env_live.is_file():  # only the single key we need; nothing else is read or kept
        for line in env_live.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


@pytest.fixture(scope="module")
def ledger() -> BudgetLedger:
    try:
        budget = load_budget(
            Path(os.environ.get("MOODPRINT_EVAL_BUDGET", DEFAULT_BUDGET_PATH)), scope=SCOPE
        )
    except BudgetError as error:
        pytest.exit(f"BLOCKED: {error}", returncode=3)
    if _api_key() is None:
        pytest.exit("BLOCKED: OPENAI_API_KEY is not set", returncode=3)
    return BudgetLedger(budget)


@pytest.fixture
async def client(ledger: BudgetLedger):
    http = httpx.AsyncClient(
        transport=GuardedTransport(
            httpx.AsyncHTTPTransport(), ledger, run_id=f"live-compat-{uuid4().hex[:8]}"
        ),
        timeout=60,
    )
    client = AsyncOpenAI(api_key=_api_key(), max_retries=0, http_client=http)  # no hidden retries
    try:
        yield client
    finally:
        await http.aclose()


def _ctx(cfg: AppConfig, budget_calls: int = 4) -> CompanionToolContext:
    from types import SimpleNamespace
    from typing import cast

    from moodprint_shared.contracts.agent import AgentServices

    return CompanionToolContext(
        auth=AuthContext(uuid4(), "live-compat", "aal1", "{}"),
        request_id="live-compat",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace(knowledge=FixtureKnowledgeRetriever())),
        context=ContextBundle(),
        budget=RunToolBudget(budget_calls),
    )


def _cfg(ledger: BudgetLedger) -> AppConfig:
    from dataclasses import replace

    cap = ledger.budget.max_output_tokens_per_request
    base = AppConfig()
    return replace(
        base, agent=replace(base.agent, max_output_tokens=min(base.agent.max_output_tokens, cap))
    )


async def test_l_ag_01_vietnamese_streaming_turn(client, ledger) -> None:
    from agents import SQLiteSession

    cfg = _cfg(ledger)
    runtime = CompanionRuntime(cfg, build_registry(cfg), openai_client=client)
    ctx = _ctx(cfg)
    events = [
        e
        async for e in runtime.stream_turn(
            ctx=ctx,
            user_input="Chào bạn, hôm nay mình hơi mệt.",
            session=SQLiteSession(str(ctx.conversation_id)),
        )
    ]
    names = [e.event for e in events]
    assert "message.delta" in names and names[-1] == "run.completed", names
    usage = next(e for e in events if e.event == "run.usage").data
    assert usage.total_tokens > 0 and OPENAI_MODEL == "gpt-6-luna"


async def test_l_ag_02_one_function_tool_round_trip(client, ledger) -> None:
    from agents import SQLiteSession

    cfg = _cfg(ledger)
    runtime = CompanionRuntime(cfg, diagnostic_registry(), openai_client=client)
    ctx = _ctx(cfg)
    events = [
        e
        async for e in runtime.stream_turn(
            ctx=ctx,
            user_input="Hãy dùng công cụ để xem giờ máy chủ rồi trả lời ngắn.",
            session=SQLiteSession(str(ctx.conversation_id)),
        )
    ]
    assert [e.data.tool for e in events if e.event == "tool.started"] == ["get_server_time"]
    assert events[-1].event == "run.completed"


async def test_l_ag_03_small_structured_output(client, ledger) -> None:
    from pydantic import BaseModel

    class Tiny(BaseModel):
        reply: str
        urgency: str

    response = await client.responses.parse(
        model=OPENAI_MODEL,
        input="Trả lời JSON: reply là lời chào ngắn tiếng Việt, urgency là 'none'.",
        text_format=Tiny,
        store=False,
        max_output_tokens=ledger.budget.max_output_tokens_per_request,
        reasoning={"effort": "low"},
    )
    assert response.output_parsed is not None and response.output_parsed.urgency in {
        "none",
        "elevated",
        "immediate",
    }


@pytest.mark.skip(reason="NOT_IMPLEMENTED: L-AG-04 needs evidence/reader.py (P3-09)")
async def test_l_ag_04_image_input() -> None: ...


@pytest.mark.skip(
    reason="NOT_IMPLEMENTED: L-AG-05 approval resume in a new process with the real model"
)
async def test_l_ag_05_approval_resume_with_real_model() -> None: ...


@pytest.mark.skip(reason="NOT_IMPLEMENTED: L-AG-06 compaction session needs the P3-08 policy")
async def test_l_ag_06_compaction_session() -> None: ...
