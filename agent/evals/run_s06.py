"""Original S-06 structured-mechanism experiment. Default is an offline plan only.

No paid call can occur without --live and the existing cumulative budget/ledger.
Mechanism outputs are not urgency-architecture A/B/C results or production safety certification.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.budget import BudgetError
from evals.s06_mechanisms import build_plan, compare_mechanisms
from evals.s06_runner import OpenAIExtractionProvider, run_slot


async def execute(plan, args):
    from evals.live import EVAL_SCOPE, live_cfg, metered_client, open_ledger

    os.environ["MOODPRINT_EVAL_BUDGET"] = str(args.budget)
    os.environ["MOODPRINT_EVAL_LEDGER"] = str(args.ledger)
    ledger = open_ledger(EVAL_SCOPE)
    # Refuse the entire continuation before constructing a provider if allowance is exhausted.
    if ledger.reserved_calls >= ledger.budget.max_calls_total:
        raise BudgetError("cumulative call cap exhausted")
    before = (ledger.reserved_calls, ledger.committed_usd, ledger.spent_tokens)
    rows = []
    for slot in plan["slots"]:
        label = f"s06-{slot['case_id']}-{slot['mechanism']}-{slot['repeat']}"
        client, http = metered_client(ledger, label)
        try:
            row = await run_slot(plan, slot, OpenAIExtractionProvider(client, live_cfg(ledger)))
            rows.append(row)
        finally:
            await http.aclose()
        if row.get("blocked"):
            break
    after = (ledger.reserved_calls, ledger.committed_usd, ledger.spent_tokens)
    return rows, dict(
        calls=after[0] - before[0],
        committed_usd=after[1] - before[1],
        tokens=after[2] - before[2],
        cumulative_calls=after[0],
        cumulative_usd=after[1],
        unknown_calls=ledger.unknown_calls,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--budget", type=Path, default=Path(".local/eval-budget.json"))
    p.add_argument("--ledger", type=Path, default=Path(".local/eval-spend.jsonl"))
    args = p.parse_args()
    plan = build_plan(repeat=3)
    rows = []
    usage = dict(calls=0, status="NOT_RUN")
    code = 0
    if args.live:
        try:
            rows, usage = asyncio.run(execute(plan, args))
        except BudgetError as error:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 3
        code = 1  # Real outputs still require explicit human/coding-agent rubric grades.
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "outputs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    (args.out / "usage.json").write_text(json.dumps(usage, indent=2) + "\n", encoding="utf-8")
    (args.out / "status.json").write_text(
        json.dumps(compare_mechanisms(plan, rows, []), indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(rows)}/{len(plan['slots'])} slots executed; graded live comparison NOT_VERIFIED")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
