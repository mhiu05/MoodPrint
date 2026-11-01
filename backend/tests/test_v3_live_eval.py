"""V3 live evaluation with the real model (gpt-6-luna). Skipped unless explicitly enabled.

    MOODPRINT_V3_LIVE=1 V3_LIVE_MAX_USD=1.0 V3_LIVE_OUTPUT=results.json OPENAI_API_KEY=... pytest tests/test_v3_live_eval.py

Generation uses only the configured live model; judging is the coded judge in evals/v3/judge.py.
Every real model call is wrapped by a recording Model so privacy is checked on the actual
inputs each role received. Spend is read back from ai_usage and stops the run at the cap.
"""

import asyncio
import json
import os
import time
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from agents import Model
from sqlalchemy import func, select

from evals.v3.cases import CASES, GROUP_TURNS, HISTORY_CANARY, JOURNAL, JOURNAL_CANARY
from evals.v3.judge import judge_group, judge_turn, phase2_baseline

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(os.environ.get("MOODPRINT_V3_LIVE") != "1", reason="live evaluation is opt-in (costs money)"),
]
ROLES = ("planner", "dieuphoi", "nhatky", "hoatdong", "nhatky:consult", "hoatdong:consult", "selector")


class RecordingModel(Model):
    """Delegates to the real model; keeps the inputs a role actually sent (in memory only)."""

    def __init__(self, inner: Model, role: str, log: list):
        self.inner, self.role, self.log = inner, role, log

    async def get_response(self, *args, **kwargs):
        raise AssertionError("The application uses the SDK streaming path")

    async def stream_response(self, *args, **kwargs):
        self.log.append({"role": self.role, "text": (args[0] or "") + json.dumps(args[1], ensure_ascii=False)})
        async for event in self.inner.stream_response(*args, **kwargs):
            yield event


def api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key and os.environ.get("V3_LIVE_ENV_FILE"):
        for line in Path(os.environ["V3_LIVE_ENV_FILE"]).read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key


async def spent(app, run_ids: list[UUID]) -> dict:
    from app.infrastructure.database.models import AiRun, AiUsage

    async with app.state.database.sessions() as db:
        ids = list(run_ids) + list((await db.scalars(select(AiRun.id).where(AiRun.parent_run_id.in_(run_ids)))).all())
        row = (await db.execute(select(
            func.coalesce(func.sum(AiUsage.requests_started), 0), func.coalesce(func.sum(AiUsage.input_tokens), 0),
            func.coalesce(func.sum(AiUsage.output_tokens), 0), func.coalesce(func.sum(AiUsage.estimated_nano_usd), 0),
        ).where(AiUsage.run_id.in_(ids)))).one()
    return {"requests": int(row[0]), "input_tokens": int(row[1]), "output_tokens": int(row[2]),
            "usd": int(row[3]) / 1e9}


async def total_spent(app) -> float:
    from app.infrastructure.database.models import AiUsage

    async with app.state.database.sessions() as db:
        return int(await db.scalar(select(func.coalesce(func.sum(AiUsage.estimated_nano_usd), 0)))) / 1e9


async def run_steps(app, run_id) -> list[dict]:
    from app.ai.orchestration.models import AiOrchestrationStep

    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiOrchestrationStep).where(AiOrchestrationStep.workflow_run_id == run_id))).all()
    return [{"kind": r.kind, "target_bot": r.target_bot, "status": r.status, "deny_reason": r.deny_reason,
             "failure_code": r.failure_code, "detail": r.detail} for r in rows]


async def test_v3_live_evaluation(clients):
    from app.ai.provider import SdkProvider
    from app.modules.journal.models import JournalEntry
    from tests.collaboration_helpers import local_today
    from tests.group_helpers import create_group
    from tests.orchestration_helpers import key, v3_setup

    cap = float(os.environ.get("V3_LIVE_MAX_USD", "0"))
    secret = api_key()
    assert cap > 0 and secret, "needs V3_LIVE_MAX_USD > 0 and an API key"
    app, [(client, uid), _] = clients
    await v3_setup(app, client, edges=("dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong", "dieuphoi_handoff_nhatky"))
    settings = app.state.settings
    settings.ai_group_chat_enabled = True
    settings.ai_accounting_enabled = True
    settings.openai_model = os.environ.get("V3_LIVE_MODEL", "gpt-6-luna")
    settings.openai_api_key = __import__("pydantic").SecretStr(secret)
    settings.ai_enabled = True
    settings.ai_timeout_seconds = 60
    async with app.state.database.sessions.begin() as db:
        for days, text, emotions, factors in JOURNAL:
            db.add(JournalEntry(user_id=uid, local_date=local_today() - timedelta(days=days), timezone="Asia/Ho_Chi_Minh",
                                mood=2, text=text, emotions=emotions, factors=factors, status="saved"))
    from agents.models.openai_responses import OpenAIResponsesModel

    provider: SdkProvider = app.state.ai.provider
    real = OpenAIResponsesModel(settings.openai_model, provider._openai(secret))
    log: list = []
    app.state.ai.agent_model_overrides = {role: RecordingModel(real, role, log) for role in ROLES}
    app.state.ai.model_override = RecordingModel(real, "direct", log)

    results: dict = {"model": settings.openai_model, "cases": [], "group": [], "stopped": None}
    only = {item for item in os.environ.get("V3_LIVE_CASES", "").split(",") if item}
    for case in [case for case in CASES if not only or case.id in only]:
        if await total_spent(app) >= cap:
            results["stopped"] = f"cap reached before {case.id}"
            break
        created = await client.post("/api/v1/ai/conversations", json={"botId": "dieuphoi"}, headers=key())
        url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
        runs = []
        if case.id == "h1":
            runs.append(await send(app, client, url, f"Chào, mình tên là {HISTORY_CANARY}"))
        log.clear()
        started = time.monotonic()
        run = await send(app, client, url, case.text)
        latency = time.monotonic() - started
        view = (await client.get(url)).json()
        last = view["messages"][-1] if view["messages"] else {}
        last_run = last.get("runId")
        texts = [m["text"] for m in view["messages"] if m["actor"] == "bot" and m["runId"] == last_run]
        row = {
            "id": case.id, "text": case.text, "expect": list(case.expect), "held_out": case.held_out,
            "adversarial": case.adversarial, "tags": list(case.tags), "status": run.terminal_status,
            "failure": run.failure, "latency_s": round(latency, 2), "reply": texts,
            "speaker": last.get("speaker"), "steps": await run_steps(app, run.id),
            "usage": await spent(app, [run.id, *[r.id for r in runs]]),
            "journal_canary_outside_nhatky": any(
                JOURNAL_CANARY in item["text"] for item in log if item["role"] not in ("nhatky:consult", "nhatky")),
            "history_canary_in_handoff": any(
                HISTORY_CANARY in item["text"] for item in log if item["role"] == "nhatky"),
            "roles_called": [item["role"] for item in log],
            "phase2": phase2_baseline(case),
        }
        row["judge"] = judge_turn({"expect": list(case.expect), "tags": list(case.tags)}, row)
        results["cases"].append(row)

    if await total_spent(app) < cap and os.environ.get("V3_LIVE_GROUP", "1") == "1":
        group = await create_group(client, name="Nhóm đánh giá")
        for text, acceptable in GROUP_TURNS:
            if await total_spent(app) >= cap:
                results["stopped"] = "cap reached in group turns"
                break
            before = {m["id"] for m in (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()["messages"]}
            log.clear()
            started = time.monotonic()
            run = await say_group(app, client, group["groupId"], text)
            latency = time.monotonic() - started
            view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
            new = [(m["speaker"], m["text"]) for m in view["messages"] if m["actor"] == "bot" and m["id"] not in before]
            turn = {"text": text, "acceptable": acceptable, "status": run.terminal_status, "latency_s": round(latency, 2),
                    "messages": new, "steps": await run_steps(app, run.id), "usage": await spent(app, [run.id]),
                    "journal_canary_leak": any(JOURNAL_CANARY in item["text"] for item in log),
                    "roles_called": [item["role"] for item in log]}
            turn["judge"] = judge_group(turn)
            results["group"].append(turn)
    results["total_usd"] = await total_spent(app)
    output = Path(os.environ.get("V3_LIVE_OUTPUT", "v3-live-results.json"))
    await asyncio.to_thread(output.write_text, json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    assert results["total_usd"] <= cap * 1.1


async def send(app, client, url, text):
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", headers={"Idempotency-Key": str(uuid4())}, json={
        "text": text, "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]})
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 120)
    return run


async def say_group(app, client, group_id, text):
    from tests.group_helpers import say

    run, _ = await say(app, client, group_id, text, wait=False)
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 180)
    return run
