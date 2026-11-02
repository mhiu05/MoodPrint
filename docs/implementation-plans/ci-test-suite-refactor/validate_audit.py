"""Offline self-check of this audit package; source and evidence are read-only."""
import csv
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from audit_inventory import browser_items, read

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REQUIRED = (
    "00-executive-summary.md", "01-test-suite-inventory.md",
    "02-ci-baseline-and-bottlenecks.md", "03-target-test-architecture.md",
    "04-target-ci-architecture.md", "05-production-compatibility-gates.md",
    "06-refactor-implementation-plan.md", "07-validation-and-benchmark-plan.md",
    "08-agent-implementation-handoff.md",
)


def validate():
    failures = []
    links = 0
    for name in REQUIRED:
        if not (HERE / name).is_file() or not read(HERE / name).strip():
            failures.append("Missing/empty required document: " + name)
    for path in HERE.rglob("*.md"):
        fenced = False
        for line_no, line in enumerate(read(path).splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            if fenced:
                continue
            for target in re.findall(r"!?\[[^\]\n]*\]\(([^\s)]+)\)", line):
                url = urlsplit(target.strip("<>"))
                if url.scheme or url.netloc or not url.path:
                    continue
                links += 1
                if not (path.parent / unquote(url.path)).resolve().exists():
                    failures.append(f"Broken link {path.name}:{line_no}: {target}")
    evidence = HERE / "evidence"
    parsed = {p.name: json.loads(read(p)) for p in evidence.glob("*.json")}
    inventory = parsed["test-inventory.json"]
    tests = inventory["tests"]
    with (evidence / "test-inventory.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != len(tests) or len(tests) != inventory["summary"]["rows"]:
        failures.append("CSV/JSON inventory row count mismatch")
    counts = {
        "pytest": len(parsed["pytest-manifest.json"]["items"]),
        "Vitest": len(parsed["vitest-collection.json"]),
        "Playwright": sum(len(browser_items(parsed[n])) for n in ("playwright-e2e-collection.json", "playwright-fullstack-collection.json")),
    }
    for framework, count in counts.items():
        actual = sum(row["collected_cases"] or 0 for row in tests if row["framework"] == framework)
        if count != actual:
            failures.append(f"Collector/inventory mismatch for {framework}: {count} != {actual}")
    if counts["Vitest"] != parsed["vitest-local-run.json"]["numTotalTests"]:
        failures.append("Dynamic Vitest list and local execution total differ")
    for row in tests:
        if not (ROOT / row["test_path"]).is_file():
            failures.append("Inventory source missing: " + row["test_path"])
    plan = read(HERE / REQUIRED[6])
    sections = re.split(r"^### (P[0-6]-\d+) — ", plan, flags=re.MULTILINE)
    tasks = {}
    fields = ("Priority", "Objective", "Files", "Dependencies", "Implementation steps", "Acceptance criteria", "Tests to run", "Expected impact", "Risks", "Rollback")
    for index in range(1, len(sections), 2):
        task_id, body = sections[index:index + 2]
        if task_id in tasks:
            failures.append("Duplicate task ID: " + task_id)
        for field in fields:
            if f"**{field}:**" not in body:
                failures.append(f"{task_id} missing required field {field}")
        if "- [ ] " not in body:
            failures.append(task_id + " lacks executable checkbox steps")
        match = re.search(r"\*\*Dependencies:\*\*([^\n]*)", body)
        tasks[task_id] = re.findall(r"P[0-6]-\d+", match.group(1)) if match else []
    visiting, visited = set(), set()
    def visit(task_id):
        if task_id in visiting:
            failures.append("Cyclic task dependency: " + task_id)
            return
        if task_id in visited:
            return
        if task_id not in tasks:
            failures.append("Unknown dependency: " + task_id)
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in tasks:
        visit(task_id)
    if len(tasks) != 18 or {i[:2] for i in tasks} != {f"P{i}" for i in range(7)}:
        failures.append("Expected 18 tasks across P0–P6")
    stats = {"required_documents": len(REQUIRED), "local_links_checked": links, "json_files_parsed": len(parsed), "inventory_rows": len(tests), "collected_cases": counts, "tasks": len(tasks), "task_fields_including_id": len(fields) + 1, "failures": failures}
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(validate())
