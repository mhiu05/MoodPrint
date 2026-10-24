"""Check MoodPrint plan integrity without dependencies or network access.

Read-only by default. Pass --write to refresh the current documentation report;
the original audit report is retained as explicitly historical evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

DOCUMENTS = (
    "README.md", "00-executive-summary.md", "01-codebase-audit.md",
    "02-gap-analysis.md", "03-target-architecture.md", "04-agents-sdk-architecture.md",
    "05-backend-data-realtime-plan.md", "06-frontend-integration-plan.md",
    "07-implementation-roadmap.md", "08-testing-evals-plan.md",
    "09-security-devops-plan.md", "10-decisions-and-open-questions.md",
)
EXPECTED_DEPENDENCIES = {
    "P00.01": [], "P00.02": ["P00.01"], "P00.03": ["P00.02"], "P00.04": ["P00.03"],
    "P01.01": ["P00.03", "P00.04"], "P01.02": ["P01.01"],
    "P01.03": ["P01.02"], "P01.04": ["P01.03"],
    "P02.01": ["P01.03"], "P02.02": ["P02.01"],
    "P02.03": ["P02.02"], "P02.04": ["P02.03"],
    "P03.01": ["P02.03"], "P03.02": ["P03.01", "P02.04"], "P03.03": ["P03.02"],
    "P04.01": ["P01.04", "P03.02"], "P04.02": ["P04.01", "P03.03"],
    "P04.03": ["P04.02"], "P04.04": ["P04.03"],
    "P05.00": ["P01.03", "P01.04", "P00.04"], "P05.01": ["P05.00"],
    "P05.02": ["P05.01", "P01.03"], "P05.03": ["P05.02"],
    "P06.01": ["P05.02", "P05.00", "P01.03"], "P06.02": ["P06.01"],
    "P06.03": ["P06.02"], "P06.04": ["P06.03", "P05.00"],
    "P06.05": ["P06.02", "P06.04"], "P07.01": ["P02.03", "P01.03"],
    "P07.02": ["P07.01", "P03.02"],
    "P07.03": ["P04.04", "P04.02", "P05.01", "P05.03", "P06.05", "P07.02"],
    "P07.04": ["P07.03"], "P08.01": ["P07.03"],
    "P08.02": ["P04.04", "P03.03", "P02.04"], "P08.03": ["P07.03", "P06.03"],
    "P08.04": ["P08.01", "P08.02"], "P09.01": ["P08.01", "P08.03"],
    "P09.02": ["P08.02", "P08.03", "P08.04"], "P09.03": ["P09.01", "P09.02"],
}
EXPECTED_TESTS = {
    f"T-{prefix}-{number:02}"
    for prefix, count in {
        "BASE": 1, "CONTRACT": 1, "AUTH": 2, "CONSENT": 1, "PRIV": 2,
        "AI": 6, "MOOD": 2, "MEM": 4, "MATCH": 3, "CONN": 2, "MSG": 3,
        "REVEAL": 2, "SAFE": 2, "VOICE": 2, "UI": 2, "JOB": 2, "OPS": 2,
        "EVAL": 2, "PERF": 1,
    }.items()
    for number in range(1, count + 1)
} | {"T-API-02"}
TASK = re.compile(r"\bP\d{2}\.\d{2}\b")
TEST = re.compile(r"\bT-[A-Z]+-\d{2}\b")
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")


def heading_ids(content: str) -> set[str]:
    counts: Counter[str] = Counter()
    result = set()
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if match:
            slug = re.sub(r"[^\w\- ]", "", match[1].lower()).replace(" ", "-")
            result.add(slug if not counts[slug] else f"{slug}-{counts[slug]}")
            counts[slug] += 1
    return result


def check(root: Path) -> dict:
    plans = root / "docs/plans"
    errors: list[str] = []
    documents = {}
    for name in DOCUMENTS:
        path = plans / name
        if not path.is_file():
            errors.append(f"Missing plan: {name}")
        else:
            documents[name] = path.read_text(encoding="utf-8-sig")

    tasks = {}
    task_occurrences: Counter[str] = Counter()
    roadmap = documents.get("07-implementation-roadmap.md", "")
    for line in roadmap.splitlines():
        match = re.match(r"^- \[[ xX]\] \*\*(P\d{2}\.\d{2})\b", line)
        if not match:
            continue
        task_id = match[1]
        task_occurrences[task_id] += 1
        if "Depends:" not in line:
            errors.append(f"{task_id}: missing explicit Depends field")
            tasks[task_id] = []
        else:
            tasks[task_id] = list(dict.fromkeys(TASK.findall(line.split("Depends:", 1)[1])))
        if "Acceptance" not in line and "Test T-" not in line:
            errors.append(f"{task_id}: missing acceptance/test criteria")
    for task_id, count in task_occurrences.items():
        if count != 1:
            errors.append(f"Duplicate task definition: {task_id} ({count})")
    if set(tasks) != set(EXPECTED_DEPENDENCIES):
        errors.append(f"Task IDs changed: missing={sorted(set(EXPECTED_DEPENDENCIES)-set(tasks))}, "
                      f"extra={sorted(set(tasks)-set(EXPECTED_DEPENDENCIES))}")
    for task_id in tasks.keys() & EXPECTED_DEPENDENCIES.keys():
        if set(tasks[task_id]) != set(EXPECTED_DEPENDENCIES[task_id]):
            errors.append(f"{task_id}: dependency baseline changed: {tasks[task_id]}")

    visited, visiting = set(), set()
    acyclic = True

    def visit(task_id: str) -> None:
        nonlocal acyclic
        if task_id in visiting:
            acyclic = False
            errors.append(f"Dependency cycle through {task_id}")
            return
        if task_id in visited:
            return
        if task_id not in tasks:
            errors.append(f"Undefined dependency: {task_id}")
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)

    test_rows = re.findall(r"^\|\s*(T-[A-Z]+-\d{2})\s*\|", documents.get("08-testing-evals-plan.md", ""), re.M)
    if set(test_rows) != EXPECTED_TESTS or len(test_rows) != len(EXPECTED_TESTS):
        errors.append(f"Test IDs changed/duplicated: missing={sorted(EXPECTED_TESTS-set(test_rows))}, "
                      f"extra={sorted(set(test_rows)-EXPECTED_TESTS)}, rows={len(test_rows)}")
    local_links = line_anchors = 0
    for name, content in documents.items():
        unknown_tasks = set(TASK.findall(content)) - set(EXPECTED_DEPENDENCIES)
        unknown_tests = set(TEST.findall(content)) - EXPECTED_TESTS
        if unknown_tasks or unknown_tests:
            errors.append(f"{name}: undefined IDs: {sorted(unknown_tasks | unknown_tests)}")
        fence_char = None
        fence_length = 0
        for lineno, line in enumerate(content.splitlines(), 1):
            fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
            if fence:
                marker, suffix = fence.groups()
                if fence_char is None:
                    fence_char, fence_length = marker[0], len(marker)
                elif marker[0] == fence_char and len(marker) >= fence_length and not suffix.strip():
                    fence_char = None
                continue
            if fence_char:
                continue
            for link in LINK.findall(line):
                target = link.strip().strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                path = (plans / name).parent / unquote(parsed.path) if parsed.path else plans / name
                local_links += 1
                if not path.exists():
                    errors.append(f"{name}:{lineno}: broken local link {target}")
                    continue
                if not parsed.fragment or not path.is_file():
                    continue
                fragment = unquote(parsed.fragment)
                anchor = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", fragment)
                target_content = path.read_text(encoding="utf-8-sig") if path.suffix in {".md", ".ts", ".tsx", ".css", ".py", ".json"} else ""
                if anchor:
                    line_anchors += 1
                    if not (1 <= int(anchor[1]) <= len(target_content.splitlines())):
                        errors.append(f"{name}:{lineno}: source line out of range {target}")
                elif path.suffix == ".md" and fragment not in heading_ids(target_content):
                    errors.append(f"{name}:{lineno}: missing heading {target}")
        if fence_char:
            errors.append(f"{name}: unclosed Markdown code fence")
        active = content
        if name == "01-codebase-audit.md":
            continue
        if name == "08-testing-evals-plan.md":
            active = content.split("## Validation lịch sử", 1)[0]
        for pattern in (
            r"TypeScript Modular Monolith", r"Modular Monolith TypeScript", r"backend TypeScript theo",
            r"Agents SDK TypeScript", r"TypeScript Agents SDK", r"\bFastify\b", r"\bSocket\.IO\b",
            r"backend/package\.json", r"packages/contracts", r"backend/src/", r"```ts\b",
            r"needsApproval", r"maxTurns", r"npm\.cmd exec --workspace backend", r"backend/tests/[^`\s]+\.ts\b",
            r"OpenAI OpenAI", r"mock mode có banner", r"demo riêng có banner", r"banner real/synthetic",
        ):
            if re.search(pattern, active):
                errors.append(f"{name}: stale active stack requirement matching {pattern}")
        if "Python" not in active or "Supabase" not in active:
            errors.append(f"{name}: missing chosen stack context")

    architecture = documents.get("03-target-architecture.md", "")
    for required in ("Python 3.12", "FastAPI", "Pydantic", "SQLAlchemy", "psycopg 3", "Alembic", "frontend/src/api/generated", "SANDBOX_ENABLED=false"):
        if required not in architecture:
            errors.append(f"Architecture missing {required}")
    return {
        "checkedAt": datetime.now(UTC).isoformat(),
        "status": "FAIL" if errors else "PASS",
        "scope": "Current documentation integrity only; no backend, provider, SQL or cloud verification claims",
        "documentCount": len(documents), "taskCount": len(tasks), "plannedTestIdCount": len(test_rows),
        "localLinksChecked": local_links, "sourceLineAnchorsChecked": line_anchors,
        "balancedCodeFences": not any("fence" in error for error in errors),
        "dependencyGraph": {"acyclic": acyclic, "baselinePreserved": all(set(tasks.get(key, [])) == set(value) for key, value in EXPECTED_DEPENDENCIES.items()), "tasks": tasks},
        "documentHashes": {name: hashlib.sha256((plans/name).read_bytes()).hexdigest() for name in documents},
        "errors": errors, "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true", help="Refresh current report, retaining previous audit as historical")
    parser.add_argument("--json", action="store_true", help="Print complete report")
    args = parser.parse_args()
    report = check(args.root.resolve())
    if args.write:
        target = args.root / "docs/plans/validation-artifacts/document-checks.json"
        old = json.loads(target.read_text(encoding="utf-8-sig")) if target.exists() else {}
        historical = old.get("historicalAudit")
        if historical is None and old.get("sourcePreservation"):
            historical = old
        if historical:
            report["historicalAudit"] = historical
            report["historicalAuditScope"] = "Original audit 2026-10-23 before implementation; hashes/test results apply only to that snapshot, never to current source"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']}: {report['documentCount']} plans; {report['taskCount']} tasks; {report['plannedTestIdCount']} planned test IDs; {report['localLinksChecked']} local links; DAG {'acyclic' if report['dependencyGraph']['acyclic'] else 'CYCLIC'}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
