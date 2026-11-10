"""Evaluation runner.

    uv run python agent/evals/run.py --suite deterministic
    uv run python agent/evals/run.py --suite live --budget .local/eval-budget.json --repeat 1 --effort low

``deterministic`` is free and offline. ``live`` refuses to start (exit 3) without the owner's
budget and key, reserves worst-case cost before every request, and never uses a model as judge:
it records outputs and deterministic assertions; the coding agent writes ``grades.jsonl``.
"""

import argparse
import asyncio
import importlib
import json
import os
import subprocess
import sys
from contextlib import AsyncExitStack
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import assertions, safety_eval  # noqa: E402
from evals.budget import EXIT_BUDGET, BudgetError  # noqa: E402
from evals.cases_io import CASE_DIR, Case, load_cases  # noqa: E402
from evals.provenance import build_manifest, digest  # noqa: E402
from moodprint_agent.companion import PROMPT_VERSION  # noqa: E402
from moodprint_agent.tools.factory import build_registry  # noqa: E402
from moodprint_shared.config import OPENAI_MODEL, AppConfig  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def check_record(case: Case, record: dict[str, Any]) -> list[assertions.Result]:
    if not record.get("turns") or record.get("blocked") or record.get("crashed"):
        return [assertions.Result("A-EXEC", False, True, "case did not execute successfully")]
    return (
        assertions.check_screenshot(record)
        if case.suite == "screenshot"
        else assertions.check(case, record)
    )


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


def selected_cases(args: argparse.Namespace) -> list[Case]:
    groups = [g for g in args.groups.split(",") if g] if args.groups else []
    cases = [c for c in load_cases(*groups) if not args.case or c.id in args.case.split(",")]
    if not cases:
        raise ValueError("selection contains no cases")
    if args.case and set(args.case.split(",")) != {c.id for c in cases}:
        raise ValueError("unknown or excluded case id")
    return cases


def planned_manifest(args: argparse.Namespace, cfg: AppConfig) -> dict[str, Any]:
    manifest = build_manifest(
        selected_cases(args),
        repeat=args.repeat,
        cfg=cfg,
        effort=args.effort,
        retriever=args.retriever,
        corpus_version=args.corpus_version,
        corpus_sha256=args.corpus_sha256,
    )
    manifest["retriever_factory"] = args.retriever_factory
    return manifest


def plan_only(args: argparse.Namespace) -> int:
    # Deliberately before budget/key loading. It cannot create a ledger or HTTP client.
    manifest = planned_manifest(args, AppConfig())
    out = RESULTS / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"NOT_RUN: {len(manifest['slots'])} pinned slots; paid execution BLOCKED")
    return 0


async def live(args: argparse.Namespace) -> int:
    from evals.harness import run_case
    from evals.live import EVAL_SCOPE, live_cfg, metered_client, open_ledger

    if args.retriever == "real" and not args.retriever_factory:
        raise ValueError(
            "real retriever requires an explicit async-context-manager factory; no fixture fallback"
        )
    if args.ledger:
        os.environ["MOODPRINT_EVAL_LEDGER"] = str(Path(args.ledger))
    os.environ["MOODPRINT_EVAL_BUDGET"] = str(Path(args.budget))
    try:
        ledger = open_ledger(EVAL_SCOPE)
    except BudgetError as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return EXIT_BUDGET
    base = live_cfg(ledger)
    cfg = replace(base, agent=replace(base.agent, reasoning_effort=args.effort))
    groups = [g for g in args.groups.split(",") if g] if args.groups else []
    cases = selected_cases(args)
    manifest = planned_manifest(args, cfg)
    out = RESULTS / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    config = _config(args, cfg, groups)
    config.update(
        provenance=manifest["provenance"],
        provenance_id=manifest["provenance_id"],
        corpus_version=args.corpus_version,
        retriever=args.retriever,
    )
    (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stack = AsyncExitStack()
    knowledge = None
    if args.retriever == "real":
        module, separator, name = args.retriever_factory.partition(":")
        if not separator:
            raise ValueError("retriever factory must be module:factory")
        factory = getattr(importlib.import_module(module), name)
        knowledge = await stack.enter_async_context(factory(cfg, args.corpus_version))
        from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever

        if not isinstance(knowledge, PgVectorKnowledgeRetriever):
            raise ValueError(
                "real retriever factory must yield PgVectorKnowledgeRetriever; no fixture fallback"
            )
    before = (ledger.reserved_calls, ledger.committed_usd, ledger.spent_tokens)
    semaphore = asyncio.Semaphore(args.concurrency)
    lines: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    async def one(case: Case, repeat: int) -> None:
        async with semaphore:
            client, http = metered_client(ledger, f"{case.id}-r{repeat}")
            try:
                record = await run_case(case, repeat, cfg, client, knowledge=knowledge)
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
                    "crashed": type(error).__name__,
                }
            finally:
                await http.aclose()
            if args.retriever == "real" and any(
                v != args.corpus_version for v in record.get("retrieved_corpus_versions", [])
            ):
                record["crashed"] = "corpus_version_mismatch"
            record["provenance_id"] = manifest["provenance_id"]
            lines.append(record)
            results = check_record(case, record)
            checks.append(
                {
                    "case_id": case.id,
                    "repeat": repeat,
                    **assertions.summarize(results),
                    "provenance_id": record.get("provenance_id"),
                    "output_sha256": digest(record),
                    "results": [asdict(r) for r in results],
                }
            )

    try:
        await asyncio.gather(*(one(case, r) for case in cases for r in range(1, args.repeat + 1)))
    finally:
        await stack.aclose()
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
    if any(record.get("blocked") for record in lines):
        return EXIT_BUDGET
    return 1 if failed else 0


def reassert(args: argparse.Namespace) -> int:
    """Recompute assertions.jsonl from saved outputs: no model call, no spend."""
    base = RESULTS / args.reassert
    cases = {c.id: c for c in load_cases()}
    checks: list[dict[str, Any]] = []
    for line in (base / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        case = cases.get(record["case_id"])
        if case is None:
            continue
        results = check_record(case, record)
        checks.append(
            {
                "case_id": case.id,
                "repeat": record["repeat"],
                **assertions.summarize(results),
                "provenance_id": record.get("provenance_id"),
                "output_sha256": digest(record),
                "results": [asdict(r) for r in results],
            }
        )
    (base / "assertions.jsonl").write_text(
        chr(10).join(json.dumps(c, ensure_ascii=False) for c in checks) + chr(10),
        encoding="utf-8",
    )
    print(f"reasserted {len(checks)} outputs of {args.reassert}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("deterministic", "live"))
    parser.add_argument("--reassert", default="", help="recompute assertions for a saved run")
    parser.add_argument("--budget", default=".local/eval-budget.json")
    parser.add_argument(
        "--ledger", default="", help="existing cumulative ledger; never a fresh file"
    )
    parser.add_argument(
        "--plan-only", action="store_true", help="offline pinned NOT_RUN manifest; no providers"
    )
    parser.add_argument("--retriever", choices=("fixture", "real"), default="fixture")
    parser.add_argument(
        "--retriever-factory",
        default="",
        help="module:factory yielding an adapter in an async context manager",
    )
    parser.add_argument("--corpus-version", default="synthetic-fixture-v1")
    parser.add_argument(
        "--corpus-sha256", default="", help="published manifest digest for real corpus"
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--effort", choices=("low", "medium"), default="low")
    parser.add_argument("--groups", default="", help="comma list: chat,knowledge,injection,...")
    parser.add_argument("--case", default="", help="comma list of case ids")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.concurrency < 1:
        parser.error("repeat and concurrency must be positive")
    if args.plan_only:
        return plan_only(args)
    if args.reassert:
        return reassert(args)
    if args.suite is None:
        parser.error("--suite or --reassert is required")
    if args.suite == "deterministic":
        return deterministic(args)
    return asyncio.run(live(args))


if __name__ == "__main__":
    raise SystemExit(main())
