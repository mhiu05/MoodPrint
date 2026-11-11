"""Live compatibility smoke for ``gpt-6-luna`` + openai-agents 0.24.0 (P3-00, L-AG-01…06).

Refuses to run without an owner-approved ``.local/eval-budget.json`` and ``OPENAI_API_KEY`` (exit 3).
Every request passes through ``GuardedTransport``: Responses endpoint only, approved model,
``store=False`` and an output cap (or, for compaction, an input-bounded reservation) within the
owner's call/token/USD caps. Prompts and outputs are synthetic; the result file holds no content.
"""

import json
import subprocess
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from _live import SCOPE, live_cfg, metered_client, open_ledger
from evals.budget import BudgetError, BudgetLedger
from openai import AsyncOpenAI
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.evidence.image import prepare_image
from safevoice_agent.evidence.reader import EvidenceReader
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.context import CompanionToolContext
from safevoice_agent.tools.factory import build_registry
from safevoice_agent.tools.registry import diagnostic_registry
from safevoice_shared.config import OPENAI_MODEL, AppConfig
from safevoice_shared.contracts.agent import AgentServices
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextBundle
from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

pytestmark = pytest.mark.live_agent


@pytest.fixture(scope="module")
def ledger() -> BudgetLedger:
    try:
        return open_ledger(SCOPE)
    except BudgetError as error:
        pytest.exit(f"BLOCKED: {error}", returncode=3)


@pytest.fixture
async def client(ledger: BudgetLedger, request: pytest.FixtureRequest):
    openai, http = metered_client(ledger, request.node.name)
    try:
        yield openai
    finally:
        await http.aclose()


def _ctx(budget_calls: int = 4) -> CompanionToolContext:
    from agents import SQLiteSession  # noqa: F401  (keeps the optional import local)

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


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn"
    )


async def test_l_ag_01_vietnamese_streaming_turn(client: AsyncOpenAI, ledger, record_property):
    from agents import SQLiteSession

    cfg = live_cfg(ledger)
    runtime = CompanionRuntime(cfg, build_registry(cfg), openai_client=client)
    ctx = _ctx()
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
    record_property("total_tokens", usage.total_tokens)
    record_property("deltas", names.count("message.delta"))


async def test_l_ag_02_one_function_tool_round_trip(client: AsyncOpenAI, ledger, record_property):
    from agents import SQLiteSession

    cfg = live_cfg(ledger)
    runtime = CompanionRuntime(cfg, diagnostic_registry(), openai_client=client)
    ctx = _ctx()
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
    record_property("requests", next(e for e in events if e.event == "run.usage").data.requests)


async def test_l_ag_03_small_structured_output(client: AsyncOpenAI, ledger, record_property):
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
    assert response.output_parsed is not None
    assert response.output_parsed.urgency in {"none", "elevated", "immediate"}
    record_property("total_tokens", response.usage.total_tokens if response.usage else 0)


def _synthetic_screenshot() -> bytes:
    """256x256 PNG that says "Xin chào" (synthetic; no real person or message)."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (256, 256), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    for candidate in (
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).is_file():
            font = ImageFont.truetype(candidate, 40)
            break
    else:
        font = ImageFont.load_default(size=40)
    draw.rounded_rectangle((20, 90, 236, 160), radius=18, fill=(200, 225, 255))
    draw.text((38, 100), "Xin chào", fill=(20, 20, 20), font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_l_ag_04_image_input_reads_the_synthetic_greeting(
    client: AsyncOpenAI, ledger, record_property
):
    cfg = live_cfg(ledger)
    prepared = prepare_image(
        _synthetic_screenshot(),
        allowed_mime=cfg.agent.analysis_allowed_mime,
        max_bytes=cfg.agent.analysis_max_image_bytes,
        max_px=cfg.agent.analysis_max_image_px,
    )
    output = await EvidenceReader(client, cfg).read(prepared)
    texts = [item.text for item in output.reading.extracted_text]
    assert any("xin chao" in _fold(text) for text in texts), texts
    assert output.reading.needs_user_review is True
    record_property("total_tokens", output.usage["total_tokens"])
    record_property("diacritics_exact", any("Xin chào" in text for text in texts))
    record_property("inference_count", len(output.reading.inferences))


def test_l_ag_05_approval_resumes_in_a_new_process_with_the_real_model(
    ledger, tmp_path: Path, record_property
):
    worker = Path(__file__).with_name("_live_approval_process.py")
    env_names = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "SAFEVOICE_EVAL_BUDGET", "OPENAI_API_KEY")
    import os

    env = {name: os.environ[name] for name in env_names if name in os.environ}
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    for stage in ("start", "resume"):
        result = subprocess.run(
            [sys.executable, str(worker), stage, str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        if stage == "start":
            start = json.loads((tmp_path / "start.json").read_text(encoding="utf-8"))
            assert start[-1]["data"]["status"] == "awaiting_approval", start[-1]
            assert not (tmp_path / "executed.txt").exists()  # nothing ran before approval
            assert "process-auth-canary" not in (tmp_path / "checkpoint.json").read_text(
                encoding="utf-8"
            )
    resumed = json.loads((tmp_path / "resume.json").read_text(encoding="utf-8"))
    assert (tmp_path / "executed.txt").read_text(encoding="utf-8") == "ghi chú thử nghiệm"
    assert resumed[-1]["data"]["status"] == "completed"
    assert resumed[0]["seq"] > start[-1]["seq"]
    record_property("resume_events", len(resumed))


async def test_l_ag_06_compaction_session_on_twelve_items(
    client: AsyncOpenAI, ledger, record_property
):
    from agents import SQLiteSession
    from agents.memory import OpenAIResponsesCompactionSession

    cfg = AppConfig()
    inner = SQLiteSession("live-compaction")
    items: list = []
    for n in range(6):
        items.append({"role": "user", "content": f"Mình kể điều số {n} về buổi học hôm nay."})
        items.append(
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": f"Mình nghe điều số {n}.", "annotations": []}
                ],
            }
        )
    await inner.add_items(items)
    session = OpenAIResponsesCompactionSession(
        session_id="live-compaction",
        underlying_session=inner,
        client=client,
        model=cfg.agent.compaction_model,
        compaction_mode="input",
        should_trigger_compaction=lambda context: True,
    )
    await session.run_compaction({"compaction_mode": "input", "force": True})
    after = await inner.get_items()
    assert after, "compaction must leave a usable history"
    record_property("items_before", len(items))
    record_property("items_after", len(after))
    record_property("item_types", ",".join(sorted({str(i.get("type", "message")) for i in after})))
