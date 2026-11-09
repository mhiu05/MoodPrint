"""Summarise one evaluation run: assertions + the coding agent's grades, honestly incomplete.

    uv run python agent/evals/summarize.py --run <run-id>

Reads ``results/<run-id>/{outputs,assertions,grades}.jsonl`` and writes ``summary.md``.
An output without a grade is listed as *ungraded* and never counted as passing.
``grades.jsonl`` lines: ``{case_id, repeat, rubric_id, score 0-3, reason, grader}``.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.cases_io import load_cases  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PASS_SCORE = 2


def read(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def summarize(run_id: str) -> str:
    base = RESULTS / run_id
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    outputs = read(base / "outputs.jsonl")
    assertions = read(base / "assertions.jsonl")
    grades = read(base / "grades.jsonl")
    usage = (
        json.loads((base / "usage.json").read_text(encoding="utf-8"))
        if (base / "usage.json").is_file()
        else {}
    )
    cases = {c.id: c for c in load_cases()}

    p0_total = sum(a["p0_total"] for a in assertions)
    p0_passed = sum(a["p0_passed"] for a in assertions)
    p1_total = sum(a["p1_total"] for a in assertions)
    p1_passed = sum(a["p1_passed"] for a in assertions)
    failures = [(a["case_id"], a["repeat"], f) for a in assertions for f in a["failed"]]

    graded = {(g["case_id"], g["repeat"], g["rubric_id"]): g for g in grades}
    expected: list[tuple[str, int, str]] = []
    for output in outputs:
        case = cases.get(output["case_id"])
        if case and output.get("turns"):
            expected += [(case.id, output["repeat"], rubric) for rubric in case.rubric_ids]
    ungraded = [key for key in expected if key not in graded]
    by_rubric: dict[str, list[int]] = defaultdict(list)
    for key, grade in graded.items():
        if key in set(expected):
            by_rubric[key[2]].append(int(grade["score"]))
    low = [(k, g) for k, g in graded.items() if int(g["score"]) < PASS_SCORE]
    passing = sum(1 for k, g in graded.items() if int(g["score"]) >= PASS_SCORE)

    ttft = [
        t["ttft_ms"] for o in outputs for t in o.get("turns", []) if t.get("ttft_ms") is not None
    ]
    latency = [t["latency_ms"] for o in outputs for t in o.get("turns", [])]
    tokens = [
        t["usage"].get("total_tokens", 0)
        for o in outputs
        for t in o.get("turns", [])
        if t.get("usage")
    ]
    crashed = [o for o in outputs if o.get("crashed") or o.get("blocked")]

    lines = [
        f"# Evaluation run `{run_id}`",
        "",
        f"- model `{config['model']}` · openai-agents {config['openai_agents']} · openai {config['openai']} · "
        f"commit `{config['commit']}` · prompt `{config['prompt_version']}` · tools `{config['tools_version']}`",
        f"- effort `{config['effort']}` · repeat {config['repeat']} · groups {config['groups'] or 'all'}",
        f"- outputs: {len(outputs)} ({len(crashed)} crashed/blocked)",
        "",
        "## Deterministic assertions",
        f"- P0: **{p0_passed}/{p0_total}** passed",
        f"- P1: {p1_passed}/{p1_total} passed",
    ]
    for case_id, repeat, failure in failures:
        lines.append(f"  - FAIL {case_id} r{repeat}: {failure}")
    lines += ["", "## Rubric grades (coding agent; no judge model)"]
    for rubric in sorted(by_rubric):
        scores = by_rubric[rubric]
        lines.append(
            f"- {rubric}: mean {mean(scores):.2f} over {len(scores)} graded outputs (min {min(scores)})"
        )
    lines.append(f"- graded ≥ {PASS_SCORE}: {passing}/{len(graded)}")
    for (case_id, repeat, rubric), grade in low:
        lines.append(f"  - LOW {case_id} r{repeat} {rubric} = {grade['score']}: {grade['reason']}")
    lines.append(
        f"- **ungraded: {len(ungraded)}** of {len(expected)} expected (case, repeat, rubric)"
    )
    for case_id, repeat, rubric in ungraded[:60]:
        lines.append(f"  - ungraded {case_id} r{repeat} {rubric}")
    lines += [
        "",
        "## Latency and usage",
        f"- TTFT p50/p95 (ms): {percentile(ttft, 0.5)} / {percentile(ttft, 0.95)} (n={len(ttft)})",
        f"- turn latency p50/p95 (ms): {percentile(latency, 0.5)} / {percentile(latency, 0.95)}",
        f"- tokens per turn: mean {mean(tokens):.0f}, p95 {percentile(tokens, 0.95)}"
        if tokens
        else "- tokens: n/a",
        f"- run spend: ${usage.get('committed_usd_this_run', 'n/a')} · calls {usage.get('calls', 'n/a')} · "
        f"cumulative ledger ${usage.get('ledger_usd_total', 'n/a')} of ${usage.get('max_usd', 'n/a')}",
    ]
    text = "\n".join(lines) + "\n"
    (base / "summary.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(summarize(args.run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
