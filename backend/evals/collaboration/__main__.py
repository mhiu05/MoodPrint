"""Companion-collaboration eval (P2-09). Offline by default; live mode is paid and budget-gated.

Offline (deterministic, no model, no network):
  - routing: would a turn consult, and through which rule, versus a hand label (held-out split);
  - minimization: the specialist input of every positive case never contains the user's words;
  - fail-closed: injected/non-enum specialist outputs are rejected before the primary;
  - cost model: estimated tokens and USD per consultation from the real prompts.

    python -m evals.collaboration --offline --output report.json
    python -m evals.collaboration --live --confirm-live --max-usd 0.25 --model gpt-6-luna --output r.json

Live mode runs only the Nhịp energy specialist on the synthetic ENERGY cases through the
application's own SdkProvider.run_specialist and compares against the labels. It refuses to run
without --confirm-live, a positive --max-usd and OPENAI_API_KEY in the environment.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from evals.collaboration.cases import ENERGY, ROUTING, Energy

# USD per 1M tokens (input, cached input, output); same source as evals/proactive (2026-10-31).
PRICES = {"gpt-6-luna": (0.10, 0.01, 0.50)}
CHARS_PER_TOKEN = 3.0  # Conservative for Vietnamese (more tokens per character than English).
OUTPUT_TOKENS = 250  # Schema output plus low-effort reasoning, upper estimate.


def would_consult(bot: str, text: str) -> str | None:
    """The full content-side decision (rule match + distress gate), permissions granted."""
    from app.ai.collaboration import policy
    from app.ai.conversation import conversation_intent
    from app.ai.proactive.safety import distress_screen

    history = [{"role": "user", "content": text}]
    signals = policy.Signals(origin="chat", bot_id=bot, text=text,
                             intent=conversation_intent(bot, history, scoped=False))
    match = policy.match_rule(signals)
    if match is None or distress_screen([text]):
        return None
    return match.rule_id


def routing_report() -> dict:
    from app.ai.collaboration import policy

    rows = []
    for case in ROUTING:
        got = would_consult(case.bot, case.text)
        allowed = None
        if got is not None:
            from app.ai.conversation import conversation_intent

            match = policy.match_rule(policy.Signals(
                origin="chat", bot_id=case.bot, text=case.text,
                intent=conversation_intent(case.bot, [{"role": "user", "content": case.text}], scoped=False)))
            if match is not None and not policy.EDGES[match.edge].reads_journal:
                allowed = policy.allowed_context(match).canonical()
        leaked = bool(allowed) and any(word in allowed for word in case.text.split() if len(word) > 3)
        rows.append({"caseId": case.case_id, "bot": case.bot, "expected": case.expected, "got": got,
                     "holdout": case.holdout, "tags": list(case.tags), "ok": got == case.expected, "leaked": leaked})

    def block(items):
        positives = [r for r in items if r["expected"]]
        negatives = [r for r in items if not r["expected"]]
        fired = [r for r in items if r["got"]]
        return {
            "n": len(items),
            "accuracy": round(sum(r["ok"] for r in items) / len(items), 3),
            "recall": round(sum(r["got"] == r["expected"] for r in positives) / len(positives), 3) if positives else None,
            "precision": round(sum(r["got"] == r["expected"] for r in fired) / len(fired), 3) if fired else None,
            "unnecessaryDelegation": sum(bool(r["got"]) for r in negatives),
            "missed": [r["caseId"] for r in positives if r["got"] != r["expected"]],
            "falsePositives": [r["caseId"] for r in negatives if r["got"]],
        }

    return {"all": block(rows), "tuning": block([r for r in rows if not r["holdout"]]),
            "holdout": block([r for r in rows if r["holdout"]]),
            "leaks": [r["caseId"] for r in rows if r["leaked"]], "rows": rows}


def energy_context(case: Energy):
    from app.ai.collaboration.contracts import AllowedContext, JournalExcerpt

    day = date(2026, 10, 30)
    return AllowedContext(schema="energy-hint-in-v1", journal=tuple(
        JournalExcerpt(entry_id=uuid4(), revision=1, local_date=day, mood=mood, emotions=emotions, excerpt=text[:600])
        for mood, text, emotions in case.entries
    ))


def fail_closed_report() -> dict:
    """Schema and minimization reject every smuggling attempt, whatever the diary says."""
    from pydantic import ValidationError

    from app.ai.collaboration.contracts import EnergyHint
    from app.ai.collaboration.specialist import InvalidSpecialistOutput, validate_output

    attempts = []
    for case in ENERGY:
        allowed = energy_context(case)
        granted = [str(i) for i in allowed.granted_entry_ids()]
        candidates = [
            {"energy": "low", "time_budget_minutes": 5, "basis": "journal", "source_entry_ids": granted,
             "journal_text": case.entries[0][1]},
            {"energy": case.entries[0][1][:20] or "x", "time_budget_minutes": 5, "basis": "none", "source_entry_ids": []},
            {"energy": "high", "time_budget_minutes": 15, "basis": "journal", "source_entry_ids": [str(uuid4())]},
        ]
        for candidate in candidates:
            try:
                validate_output(EnergyHint.model_validate(candidate), allowed)
                attempts.append({"caseId": case.case_id, "rejected": False})
            except (ValidationError, InvalidSpecialistOutput):
                attempts.append({"caseId": case.case_id, "rejected": True})
    return {"attempts": len(attempts), "accepted": sum(not a["rejected"] for a in attempts)}


def cost_model() -> dict:
    from app.ai.collaboration import specialist
    from app.ai.collaboration.contracts import AllowedContext

    inputs = {
        "nhip_energy_for_rure": energy_context(ENERGY[10]).canonical(),
        "nhip_habit_for_may": AllowedContext(schema="tiny-habit-in-v1", need="sleep", time_of_day="night").canonical(),
        "rure_activity_for_guong": AllowedContext(schema="interest-activity-in-v1", interest_tag="drawing",
                                                  time_budget_minutes=10).canonical(),
    }
    price = PRICES["gpt-6-luna"]
    out = {}
    for edge, payload in inputs.items():
        tokens_in = round((len(specialist.INSTRUCTIONS[edge]) + len(specialist.INPUT_PREFIX) + len(payload)) / CHARS_PER_TOKEN)
        usd = (tokens_in * price[0] + OUTPUT_TOKENS * price[2]) / 1_000_000
        out[edge] = {"estimatedInputTokens": tokens_in, "estimatedOutputTokens": OUTPUT_TOKENS,
                     "estimatedUsdPerConsultation": round(usd, 6),
                     "estimatedUsdPer1000": round(usd * 1000, 3)}
    return {"model": "gpt-6-luna", "basis": "estimate (chars/3 per token), not measured", "edges": out}


def run_offline() -> dict:
    return {"mode": "offline", "routing": routing_report(), "failClosed": fail_closed_report(), "cost": cost_model()}


class Budget:
    def __init__(self, limit: float):
        self.limit, self.spent, self.calls = limit, 0.0, 0

    def allow(self, reserve: float) -> bool:
        return self.spent + reserve <= self.limit

    def charge(self, model: str, tokens_in: int, cached: int, tokens_out: int) -> None:
        price = PRICES[model]
        self.spent += ((tokens_in - cached) * price[0] + cached * price[1] + tokens_out * price[2]) / 1_000_000
        self.calls += 1


async def run_live(args) -> dict:
    from app.ai.collaboration import specialist
    from app.ai.collaboration.contracts import DelegationRequest
    from app.ai.provider import SdkProvider
    from app.core.config import Settings

    settings = Settings(app_env="development", ai_enabled=True, openai_model=args.model,
                        openai_api_key=os.environ["OPENAI_API_KEY"])
    provider, budget, rows = SdkProvider(settings), Budget(args.max_usd), []
    usage: dict = {}

    async def observe(event):
        if event.kind == "response_received":
            usage.update(input=event.input_tokens, cached=event.cached_input_tokens, output=event.output_tokens)

    async def nothing():
        return None

    for case in ENERGY:
        if not budget.allow(args.reserve_usd):
            break
        allowed = energy_context(case)
        request = DelegationRequest(
            collaboration_id=uuid4(), edge="nhip_energy_for_rure", rule_id="R1", requester_bot="rure",
            specialist_bot="nhip", primary_run_id=uuid4(), specialist_run_id=uuid4(),
            deadline_at=datetime.now(UTC) + timedelta(seconds=10), allowed=allowed)
        usage.clear()
        started = time.monotonic()
        try:
            hint = await specialist.run_specialist(provider, request, on_progress=nothing, observer=observe,
                                                   limit_seconds=10, user_id=uuid4())
            got, code = hint.energy, "ok"
        except Exception as error:  # noqa: BLE001 -- recorded as an outcome code, never content
            got, code = None, type(error).__name__
        budget.charge(args.model, usage.get("input", 0), usage.get("cached", 0), usage.get("output", 0))
        rows.append({"caseId": case.case_id, "expected": case.expected, "got": got, "code": code,
                     "holdout": case.holdout, "tags": list(case.tags), "seconds": round(time.monotonic() - started, 3),
                     "usage": dict(usage)})
    await provider.aclose()
    latencies = sorted(r["seconds"] for r in rows)
    return {
        "mode": "live", "model": args.model, "cases": len(rows),
        "labelAccuracy": round(sum(r["got"] == r["expected"] for r in rows) / len(rows), 3) if rows else None,
        "nonEnumOutputs": sum(r["code"] != "ok" for r in rows),
        "injectionCases": [r for r in rows if "injection" in r["tags"]],
        "latency": {"p50": statistics.median(latencies), "p95": latencies[int(0.95 * (len(latencies) - 1))]} if latencies else None,
        "spentUsd": round(budget.spent, 5), "calls": budget.calls, "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.collaboration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--max-usd", type=float, default=0.0)
    parser.add_argument("--reserve-usd", type=float, default=0.01)
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.live:
        if not args.confirm_live or args.max_usd <= 0 or not os.environ.get("OPENAI_API_KEY"):
            print("Live mode needs --confirm-live, --max-usd > 0 and OPENAI_API_KEY.", file=sys.stderr)
            return 2
        if args.model not in PRICES:
            print("Unknown model price; refusing to spend.", file=sys.stderr)
            return 2
        result = asyncio.run(run_live(args))
    else:
        result = run_offline()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {k: v for k, v in result.items() if k not in ("rows",)}
    print(json.dumps(summary if args.live else {"routing": {k: v for k, v in result["routing"].items() if k != "rows"},
                                                "failClosed": result["failClosed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
