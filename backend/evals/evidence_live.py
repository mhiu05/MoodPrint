"""Bounded real-model, multi-turn comparison against an unchanged F03 worktree.

Run as a script with --runtime-root; imports resolve from that checkout. Only a
guarded loopback *_test DB is reset. Synthetic SDK inputs are intentionally saved
for review; credentials, HTTP headers, and exception bodies are never saved.
"""
# ruff: noqa: E402 -- select the explicitly requested runtime checkout before imports

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--variant", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def evaluate(args):
    sys.path.insert(0, str(args.runtime_root.resolve() / "backend"))
    from agents.models.openai_responses import OpenAIResponsesModel
    from dotenv import dotenv_values
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.ai.prompts import instructions
    from app.ai.runtime import AiRuntime
    from app.core.config import Settings
    from app.infrastructure.database.models import Mood
    from app.main import create_app
    from evals.live import summarize_usage
    from evals.scenarios_live import prepare_database
    from tests.conftest import add_actor
    from tests.database_target import require_local_test_database
    from tests.test_chat_persistence import enable, key
    from tests.test_context_privacy import consent

    if args.output.exists():
        raise ValueError("Refusing to overwrite evaluation evidence")
    url = os.environ.get("TEST_DATABASE_URL", "")
    require_local_test_database(url)
    local = dotenv_values(REPO / "backend/.env")
    key_value = os.environ.get("OPENAI_API_KEY") or local.get("OPENAI_API_KEY")
    model_name = os.environ.get("OPENAI_MODEL") or local.get("OPENAI_MODEL")
    if not key_value or not model_name:
        raise ValueError("Real provider configuration required; no fake fallback")
    # Explicit constructor values prevent inherited hosted settings reaching this harness.
    settings = Settings(_env_file=None, app_env="test", database_url=url,
                        database_migration_url="", supabase_url="", supabase_publishable_key="",
                        openai_api_key=key_value, openai_model=model_name, ai_enabled=True,
                        ai_local_test_user_ids=[], semantic_memory_enabled=False,
                        voyage_api_key="", ai_requests_per_minute=120,
                        provider_force_ipv4=True, ai_daily_turns_per_user=200)
    frozen = json.loads((FIXTURES / "evidence_p0_baseline.json").read_text(encoding="utf-8"))
    if args.variant == "baseline" and any(instructions(bot) != text for bot, text in frozen.items()):
        raise ValueError("Baseline prompts drifted")
    dataset = json.loads((FIXTURES / "evidence_p0_cases.json").read_text(encoding="utf-8"))
    engine = await prepare_database(url)
    app = create_app(settings)
    await app.state.database.engine.dispose()
    app.state.database.engine = engine
    app.state.database.sessions = async_sessionmaker(engine, expire_on_commit=False)
    events = []
    captures = []
    budget = {"requests": 0, "reserved_token_upper_bound": 0}
    runtime_commit = await asyncio.to_thread(subprocess.check_output,
        ["git", "-C", str(args.runtime_root), "rev-parse", "HEAD"], text=True)
    report = {
        "kind": "real-provider-multiturn-evaluation", "synthetic": True,
        "variant": args.variant, "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256((FIXTURES / "evidence_p0_cases.json").read_bytes()).hexdigest(),
        "runtime_commit": runtime_commit.strip(),
        "created_at": datetime.now(UTC).isoformat(), "model": model_name,
        "sdk": importlib.metadata.version("openai-agents"),
        "configuration": {"max_output_tokens": 1200, "max_turns": 3, "retries": 0, "timeout": 30,
                          "concurrency": 1, "store": False, "tracing": False},
        "budget": {"max_requests": 60, "max_reserved_tokens": 1_000_000,
                   "maximum_estimated_usd": 0.5, "rate_snapshot": "openai-standard-2026-10-24"},
        "rows": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    class CapturingRealModel(OpenAIResponsesModel):
        async def stream_response(self, *model_args, **kwargs):
            prompt, inputs, tools, schema = model_args[0], model_args[1], model_args[3], model_args[4]
            tool_schemas = [{"name": t.name, "parameters": getattr(t, "params_json_schema", {})} for t in tools]
            # A conservative token upper bound, reserving the entire response before
            # each network call. Stop on unknown usage rather than guessing a refund.
            serialized = json.dumps({"instructions": prompt, "input": inputs, "tools": tool_schemas,
                                     "output_schema": schema.json_schema() if schema else None}, ensure_ascii=False)
            reservation = len(serialized.encode("utf-8")) + 1200 + 4096
            if budget["requests"] >= 60 or budget["reserved_token_upper_bound"] + reservation > 1_000_000:
                raise RuntimeError("Evaluation budget exhausted before network call")
            budget["requests"] += 1
            budget["reserved_token_upper_bound"] += reservation
            captures.append({"instructions": prompt, "instructions_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                             "input": inputs, "tools": [t.name for t in tools]})
            async for event in super().stream_response(*model_args, **kwargs):
                yield event

    async def observe(event):
        events.append(event)

    def configure():
        provider = app.state.ai.provider
        provider.usage_observer = observe
        app.state.ai.model_override = CapturingRealModel(model_name, provider._openai(key_value))

    async def save():
        report["usage"] = summarize_usage(events)
        usage = report["usage"]
        report["estimated_usd"] = round((usage["input_tokens"] - usage["cached_input_tokens"]) * 0.1e-6 + usage["cached_input_tokens"] * 0.01e-6 + usage["output_tokens"] * 0.5e-6, 6) if model_name == "gpt-6-luna" else None
        report["budget_consumed"] = dict(budget)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        if model_name != "gpt-6-luna":
            raise ValueError("Budget rates require reviewed pricing for this configured model")
        for index, case in enumerate(dataset["cases"]):
            client, uid = await add_actor(app, index)
            try:
                await enable(client)
                today = datetime.now(UTC).date()
                async with app.state.database.sessions.begin() as db:
                    for i, value in enumerate((3, 2, 4)[:case["records"]]):
                        db.add(Mood(user_id=uid, local_date=today - timedelta(days=(6, 0, 3)[i]),
                                    value=value, note="SYNTHETIC_PRIVATE_NOTE_DO_NOT_SEND", timezone="Asia/Bangkok"))
                if case.get("memory"):
                    from tests.test_memory import seed_proposal
                    await consent(client, "MEM", True)
                    proposal = await seed_proposal(app, uid, text=case["memory"])
                    result = await client.post(f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key())
                    assert result.status_code == 200
                configure()
                created = await client.post("/api/v1/ai/conversations", json={"botId": case["botId"], "persistent": True}, headers=key())
                assert created.status_code == 201
                url_path = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
                for turn_index, step in enumerate(case["turns"]):
                    if step.get("edit"):
                        response = await client.put(f"/api/v1/moods/{today - timedelta(days=6)}", json={"value": 5, "note": "SYNTHETIC_CORRECTED_PRIVATE_NOTE", "expectedVersion": 1}, headers=key())
                        assert response.status_code == 200
                    if step.get("revokeMemory"):
                        await consent(client, "MEM", False)
                    if step.get("restart"):
                        await app.state.ai.close()
                        app.state.ai = AiRuntime(settings, app.state.database)
                        configure()
                    view = (await client.get(url_path)).json()
                    start_capture, start_usage = len(captures), len(events)
                    started = time.perf_counter()
                    accepted = await client.post(url_path + "/messages", json={
                        "text": step["text"], "clientMessageId": str(uuid4()),
                        "expectedConversationVersion": view["version"],
                        **({"moodScope": {"fromDate": str(today - timedelta(days=6)), "toDate": str(today)}} if step.get("scope") else {}),
                    }, headers=key())
                    row = {"caseId": case["id"], "botId": case["botId"], "turn": turn_index + 1,
                           "prompt": step["text"], "variant": args.variant, "split": dataset["split"],
                           "scope_present": bool(step.get("scope")), "recorded_days": case["records"]}
                    if accepted.status_code != 202:
                        row.update(status="FAILED", admission_status=accepted.status_code)
                    else:
                        run = app.state.ai.runs[UUID(accepted.json()["runId"])]
                        await run.task
                        final = next((e.data for e in run.events if e.type == "final"), None)
                        row.update(status="COMPLETED" if run.terminal_status == "completed" else "FAILED",
                                   output=final, terminal_status=run.terminal_status,
                                   error_code=(run.failure or {}).get("code"))
                    row["latency_seconds"] = round(time.perf_counter() - started, 3)
                    row["usage"] = summarize_usage(events[start_usage:])
                    row["model_inputs"] = captures[start_capture:]
                    row["tools"] = [e.tool_name for e in events[start_usage:] if e.kind == "tool_started"]
                    serialized_inputs = json.dumps(row["model_inputs"], ensure_ascii=False)
                    row["assertions"] = {
                        "private_notes_absent": "SYNTHETIC_PRIVATE_NOTE_DO_NOT_SEND" not in serialized_inputs and "SYNTHETIC_CORRECTED_PRIVATE_NOTE" not in serialized_inputs,
                        "tool_authorization": step.get("scope", False) or "read_mood_summary" not in row["tools"],
                        "revoked_memory_absent": not step.get("revokeMemory") or "SYNTHETIC_P0_MEMORY_CANARY" not in serialized_inputs,
                        "scoped_read_executed": not step.get("scope") or "read_mood_summary" in row["tools"],
                    }
                    if args.variant == "candidate" and step.get("scope") and row.get("output"):
                        expected_count = case["records"]
                        expected_mean = {0: None, 1: "3/5", 2: "2,5/5", 3: "3/5"}[expected_count]
                        if case["id"] == "P0-NHIP-SOURCE-EDIT" and turn_index == 2:
                            expected_mean = "3,5/5"
                        row["assertions"]["grounded_count"] = f"{expected_count}/7" in row["output"]["text"]
                        row["assertions"]["grounded_mean"] = expected_mean is None or expected_mean in row["output"]["text"]
                    report["rows"].append(row)
                    await save()
                    print(json.dumps({"case": case["id"], "turn": turn_index + 1, "status": row["status"]}), flush=True)
                    if row["usage"]["unknown_usage_requests"]:
                        raise RuntimeError("Stopping bounded evaluation after unknown provider usage")
            finally:
                await client.aclose()
    except Exception as error:
        report["runner_error_type"] = type(error).__name__
        await save()
        raise
    finally:
        await app.state.ai.close()
        await engine.dispose()
    await save()
    return int(any(row["status"] != "COMPLETED" or not all(row["assertions"].values()) for row in report["rows"]))


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    raise SystemExit(asyncio.run(evaluate(arguments()), loop_factory=asyncio.SelectorEventLoop))
