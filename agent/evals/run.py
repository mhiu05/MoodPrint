"""Evaluation runner.

    uv run python agent/evals/run.py --suite deterministic
    uv run python agent/evals/run.py --suite live --budget .local/eval-budget.json --repeat 1 --effort low

``deterministic`` is free and offline. ``live`` refuses to start (exit 3) without the owner's
budget and key, reserves worst-case cost before every request, and never uses a model as judge:
it records outputs and deterministic assertions; the coding agent writes ``grades.jsonl``.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import assertions, safety_eval  # noqa: E402
from evals.budget import EXIT_BUDGET, BudgetError  # noqa: E402
from evals.cases_io import CASE_DIR, Case, load_cases  # noqa: E402
from moodprint_agent.companion import PROMPT_VERSION  # noqa: E402
from moodprint_agent.tools.factory import build_registry  # noqa: E402
from moodprint_shared.config import OPENAI_MODEL, AppConfig  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _config(args: argparse.Namespace, cfg: AppConfig, suites: list[str]) -> dict[str, Any]:
    return {
        "run_id": args.run_id,
        "suite": args.suite,
        "groups": suites,
        "repeat": args.repeat,
        "effort": args.effort,
        "model": OPENAI_MODEL,
        "openai_agents": version("openai-agents"),
        "openai": version("openai"),
        "commit": _git_commit(),
        "prompt_version": PROMPT_VERSION,
        "tools_version": build_registry(cfg).version(),
        "corpus_version": "synthetic-fixture-v1",
        "started_at": datetime.now(UTC).isoformat(),
    }


def deterministic(args: argparse.Namespace) -> int:
    cfg = AppConfig()
    out = RESULTS / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    manifest = {
        suite: [c.id for c in cases if c.suite == suite]
        for suite in sorted({c.suite for c in cases})
    }
    safety_files = sorted(CASE_DIR.glob("safety_*.jsonl"))
    safety = safety_eval.run(safety_files)
    registry = build_registry(cfg)
    names = registry.names()
    inventory = {
        "tools": sorted(names),
        "no_outbound_tool": not any(
            word in n.split("_")
            for n in names
            for word in ("send", "post", "email", "call", "submit", "share")
        ),
        "model_is_approved": OPENAI_MODEL == "gpt-6-luna",
    }
    (out / "config.json").write_text(json.dumps(_config(args, cfg, []), indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(
            {k: len(v) for k, v in manifest.items()} | {"unique": sum(map(len, manifest.values()))},
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "safety_offline.json").write_text(
        json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"run {args.run_id}")
    print(
        "manifest:",
        {k: len(v) for k, v in manifest.items()},
        "unique:",
        sum(map(len, manifest.values())),
    )
    for name, result in safety.items():
        print(
            f"{name}: n={result['n']} recall_immediate={result['recall_immediate']} "
            f"fpr={result['false_positive_rate_immediate']} misses={len(result['misses'])}"
        )
    print("inventory:", inventory)
    return 0 if inventory["no_outbound_tool"] and inventory["model_is_approved"] else 1


async def live(args: argparse.Namespace) -> int:
    from evals.harness import run_case
    from evals.live import EVAL_SCOPE, live_cfg, metered_client, open_ledger

    os.environ["MOODPRINT_EVAL_BUDGET"] = str(Path(args.budget))
    try:
        ledger = open_ledger(EVAL_SCOPE)
    except BudgetError as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return EXIT_BUDGET
    base = live_cfg(ledger)
    cfg = replace(base, agent=replace(base.agent, reasoning_effort=args.effort))
    groups = [g for g in args.groups.split(",") if g] if args.groups else []
    cases = [c for c in load_cases(*groups) if not args.case or c.id in args.case.split(",")]
    out = RESULTS / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(
        json.dumps(_config(args, cfg, groups), indent=2), encoding="utf-8"
    )
    before = (ledger.reserved_calls, ledger.committed_usd, ledger.spent_tokens)
    semaphore = asyncio.Semaphore(args.concurrency)
    lines: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    async def one(case: Case, repeat: int) -> None:
        async with semaphore:
            client, http = metered_client(ledger, f"{case.id}-r{repeat}")
            try:
                record = await run_case(case, repeat, cfg, client)
                record.update(
                    {"case_id": case.id, "suite": case.suite, "repeat": repeat, "risk": case.risk}
                )
            except BudgetError as error:
                record = {
                    "case_id": case.id,
                    "suite": case.suite,
                    "repeat": repeat,
                    "risk": case.risk,
                    "turns": [],
                    "blocked": str(error),
                }
                print(f"BLOCKED {case.id}: {error}", file=sys.stderr)
            except Exception as error:  # a crashed case is a recorded failure, never a pass
                record = {
                    "case_id": case.id,
                    "suite": case.suite,
                    "repeat": repeat,
                    "risk": case.risk,
                    "turns": [],
                    "crashed": f"{type(error).__name__}: {str(error)[:300]}",
                }
            finally:
                await http.aclose()
            lines.append(record)
            if record["turns"]:
                results = (
                    assertions.check_screenshot(record)
                    if case.suite == "screenshot"
                    else assertions.check(case, record)
                )
                summary = assertions.summarize(results)
                checks.append(
                    {
                        "case_id": case.id,
                        "repeat": repeat,
                        **summary,
                        "results": [asdict(r) for r in results],
                    }
                )

    await asyncio.gather(*(one(case, r) for case in cases for r in range(1, args.repeat + 1)))
    lines.sort(key=lambda r: (r["case_id"], r["repeat"]))
    checks.sort(key=lambda r: (r["case_id"], r["repeat"]))
    (out / "outputs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", encoding="utf-8"
    )
    (out / "assertions.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in checks) + "\n", encoding="utf-8"
    )
    after = (ledger.reserved_calls, ledger.committed_usd, ledger.spent_tokens)
    usage = {
        "calls": after[0] - before[0],
        "committed_usd_this_run": round(after[1] - before[1], 6),
        "tokens_this_run": after[2] - before[2],
        "ledger_calls_total": after[0],
        "ledger_usd_total": round(after[1], 6),
        "ledger_unknown_calls": ledger.unknown_calls,
        "max_usd": ledger.budget.max_usd,
        "prices": asdict(ledger.budget.prices),
    }
    (out / "usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    failed = sum(len(c["failed"]) for c in checks)
    print(f"run {args.run_id}: {len(lines)} outputs, {failed} failed assertions, usage {usage}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("deterministic", "live"), required=True)
    parser.add_argument("--budget", default=".local/eval-budget.json")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--effort", choices=("low", "medium"), default="low")
    parser.add_argument("--groups", default="", help="comma list: chat,knowledge,injection,...")
    parser.add_argument("--case", default="", help="comma list of case ids")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv)
    if args.suite == "deterministic":
        return deterministic(args)
    return asyncio.run(live(args))


if __name__ == "__main__":
    raise SystemExit(main())
