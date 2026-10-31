"""Run the bubble-splitting eval with one command.

Offline (default, no network): score recorded outputs from a JSONL file of
``{"caseId": ..., "output": {"messages": [...]}}`` lines.

    uv run python -m evals.multi_message --offline recorded.jsonl --output report.json

Live (paid, manual gate): calls the configured model once per case with the flag on.
It refuses to start without --confirm-live and a positive --max-usd, and stops before
the next call once the estimated spend reaches the cap. Never run against real data.

    uv run python -m evals.multi_message --live --confirm-live --max-usd 0.05 --output report.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from evals.multi_message.cases import CASES
from evals.multi_message.rubric import score, summarize


def offline(path: Path) -> dict:
    by_id = {case.case_id: case for case in CASES}
    scores = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        case = by_id.get(record.get("caseId"))
        if case is None:
            raise SystemExit(f"Unknown caseId {record.get('caseId')!r}")
        scores.append(score(case, record.get("output", {})))
    missing = sorted(set(by_id) - {item["caseId"] for item in scores})
    return {"mode": "offline", "missingCases": missing, "summary": summarize(scores), "scores": scores}


async def live(max_usd: float, *, provider=None, model_override=None) -> dict:
    from app.ai.accounting import RATES
    from app.ai.provider import SdkProvider
    from app.ai.usage import UsageEvent
    from app.core.config import Settings

    settings = Settings(ai_multi_message_enabled=True)
    provider = provider or SdkProvider(settings)
    rates = RATES.get(settings.openai_model)
    if model_override is None and rates is None:
        raise SystemExit("No pricing for the configured model; refusing an unbounded live run")
    spent_nano, cap_nano, scores = 0, int(max_usd * 1_000_000_000), []

    async def observe(event: UsageEvent):
        nonlocal spent_nano
        if event.kind == "response_received" and rates:
            spent_nano += (event.input_tokens - event.cached_input_tokens) * rates[0]
            spent_nano += event.cached_input_tokens * rates[1] + event.output_tokens * rates[2]

    async def no_progress():
        return None

    for case in CASES:
        if spent_nano >= cap_nano:
            break
        reply = await provider.run_reply(
            bot_id=case.bot_id, history=[{"role": "user", "content": case.prompt}], tools=[], context={},
            on_progress=no_progress, model_override=model_override, usage_observer=observe,
        )
        payload = {"messages": [{"text": part.text, "cards": [c.model_dump(by_alias=True) for c in part.cards]}
                                for part in reply.parts]}
        scores.append(score(case, payload))
    return {"mode": "live", "estimatedUsd": spent_nano / 1_000_000_000, "capUsd": max_usd,
            "completedCases": len(scores), "summary": summarize(scores), "scores": scores}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.multi_message")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", type=Path, metavar="RECORDED_JSONL")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--max-usd", type=float, default=0.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        print("Refusing to overwrite an existing report", file=sys.stderr)
        return 2
    if args.live:
        if not args.confirm_live or args.max_usd <= 0:
            print("Live eval needs --confirm-live and a positive --max-usd", file=sys.stderr)
            return 2
        report = asyncio.run(live(args.max_usd), loop_factory=asyncio.SelectorEventLoop)
    else:
        report = offline(args.offline)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
