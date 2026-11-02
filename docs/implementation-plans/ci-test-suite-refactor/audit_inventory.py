"""Read tracked source and audit evidence; write inventory only to --output-dir.

No source imports, provider/network calls, test execution, or database access.
Heuristic feature/layer/dependency labels require human review; collectors are authoritative.
"""
import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def read(path):
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")


def load(name, default=None):
    path = EVIDENCE / name
    return json.loads(read(path)) if path.exists() else default


def browser_items(report):
    result = []
    def visit(suite):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                result.append({"path": "frontend/tests/" + report["config"]["projects"][0]["testDir"].replace("\\", "/").rsplit("/", 1)[-1] + "/" + spec["file"].replace("\\", "/"), "title": spec["title"], "line": spec["line"], "expected_status": test.get("expectedStatus")})
        for child in suite.get("suites", []):
            visit(child)
    for suite in report.get("suites", []):
        visit(suite)
    return result


def features(path):
    rules = [("Guest", "guest"), ("Auth/session/eligibility", "auth|session|eligibility|adult|ageDeclaration"),
             ("Journal/storage", "journal"), ("AI/proactive", "proactive|checkins"),
             ("AI/orchestration/groups", "v3|orchestrat|groups|three_agent|specialist|scoped_mood"),
             ("AI/collaboration", "collaboration|sharing"), ("AI/memory", "memory|context|embedding"),
             ("Matching/social", "matching|social|profile|ranking|scoring|taxonomy|pair_alias|discovery"),
             ("Activities", "activit|quiz|icebreaker|focus"), ("Feedback/admin", "feedback|moderation|admin"),
             ("Deployment/config", "deploy/|production|runtime|database|readiness|config|artifacts"),
             ("AI/contracts", "ai_|multi_message|sdk|stream|chat|eval|live|provider"),
             ("Privacy/lifecycle", "privacy|lifecycle|retention|enforcement|safety")]
    return next((label for label, pattern in rules if re.search(pattern, path, re.I)), "Cross-feature/UI")


def build():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    pyitems = load("pytest-manifest.json", {"items": []})["items"]
    bypath = defaultdict(list)
    for item in pyitems:
        bypath[item["path"]].append(item)
    vitest = load("vitest-collection.json", [])
    for item in vitest:
        path = "frontend/" + item["file"].replace("\\", "/").split("/frontend/")[-1]
        bypath[path].append(item)
    for name in ("playwright-e2e-collection.json", "playwright-fullstack-collection.json", "playwright-tour-collection.json"):
        if name == "playwright-tour-collection.json":
            continue  # optional matrix is listed separately; do not double count default tests
        report = load(name)
        if report:
            for item in browser_items(report):
                bypath[item["path"]].append(item)
    unitrun = load("vitest-local-run.json", {})
    runtimes = {}
    for item in unitrun.get("testResults", []):
        name = "frontend/" + item["name"].replace("\\", "/").split("/frontend/")[-1]
        runtimes[name] = {"seconds": round((item["endTime"] - item["startTime"]) / 1000, 4), "scope": "local Windows Node 24; test-file execution span; not CI wall-clock"}
    rows, hashes, functions = [], defaultdict(list), []
    for name in tracked:
        if not name or name.startswith(".agents/") or name.startswith(".codex/"):
            continue
        path = ROOT / name
        ispy = bool(re.search(r"(^|/)test_[^/]+\.py$", name))
        isjs = bool(re.search(r"\.(test|spec)\.(tsx?|[cm]?js)$", name))
        custom = name.startswith("scripts/") and bool(re.search(r"/(test[_-]|check_|verify_|load_|smoke_|run_live_browser|collect_implementation_checks|export_openapi|disposable_postgres)", name))
        perf = name.startswith("frontend/tests/perf/") and name.endswith(".mjs")
        evaluator = name.startswith("backend/evals/") and name.endswith(".py") and "__" not in path.name
        if not (ispy or isjs or custom or perf or evaluator):
            continue
        source = read(path)
        pytests, imports = [], []
        if name.endswith(".py"):
            tree = ast.parse(source)
            pytests = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                    for alias in node.names:
                        candidate = node.module + "." + alias.name
                        target = ROOT / "backend" / candidate.replace(".", "/")
                        if target.with_suffix(".py").is_file() or (target / "__init__.py").is_file():
                            imported.add(candidate)
            imports = sorted(imported)
            for node in pytests:
                digest = hashlib.sha256(ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
                hashes[digest].append(f"{name}:{node.lineno}:{node.name}")
                functions.append({"path": name, "line": node.lineno, "name": node.name, "imports": imports})
        fixtures = sorted({f for item in bypath[name] for f in item.get("fixtures", [])})
        db = "database" in fixtures or bool(re.search(r"(?:TEST_DATABASE_URL|owned_scratch_database)", source))
        framework = "pytest" if name.startswith("backend/tests/") and ispy else "unittest" if name.startswith("deploy/aws/tests/") else "Vitest" if isjs and ".test.ts" in name else "Node test" if isjs and name.endswith(".cjs") else "Playwright" if isjs else "custom/eval" if evaluator else "custom"
        if name.startswith("backend/tests/"):
            ci = "Yes; verify/pytest; live/load cases conditional"
        elif framework in ("Vitest", "Node test"):
            ci = "Yes; verify/npm test" if bypath[name] or framework == "Node test" else "No; outside configured Vitest includes"
        elif name.startswith("deploy/aws/tests/"):
            ci = "Yes; verify/unittest (Linux required)"
        elif bypath[name] and framework == "Playwright":
            ci = "Yes; verify/" + ("fullstack" if "/fullstack/" in name else "test:e2e")
        elif name.endswith("onboarding-compatibility.spec.ts"):
            ci = "Conditional manual: MOODPRINT_TOUR_COMPATIBILITY=1; absent default CI"
        elif framework == "Playwright":
            ci = "No; manual separate Playwright config"
        elif name in ("scripts/load_chat_memory.py", "scripts/load_social_mood.py", "scripts/test_fullstack.py", "scripts/test_staging_proxy.sh", "scripts/check_reviewed_artifacts.py", "scripts/check_docs.py", "scripts/disposable_postgres.py", "scripts/export_openapi.py"):
            ci = "Yes; verify direct step"
        elif evaluator:
            ci = "Indirect: imported by pytest; no direct CLI step" if any(name[8:-3].replace("/", ".") in imp for f in functions for imp in f["imports"]) else "No direct CI CLI; library/manual evaluator"
        else:
            ci = "No direct CI step; manual or indirect test import"
        deps = ["PostgreSQL disposable" if db else "no DB fixture detected"]
        if fixtures:
            deps.append("fixture closure: " + ", ".join(fixtures))
        if re.search(r"monkeypatch|vi\.|route\(|Mock|fake|model_override", source):
            deps.append("mocks/fakes or browser API routes")
        if framework == "Playwright":
            deps.append("Chromium + " + ("real local API/DB + fake SDK" if "/fullstack/" in name else "mock API/Vite" if "/e2e/" in name else "manual target; review config"))
        if re.search(r"mark\.live|confirm.live|--live|OPENAI_API_KEY", source):
            deps.append("external providers only with explicit live opt-in; inspect guard")
        layer = "E2E" if framework == "Playwright" else "Integration" if db else "Unit" if ispy or isjs else "Load" if "/load_" in name or perf else "Contract" if evaluator or "/check_" in name else "Integration"
        flags = [{"line": i, "text": line.strip()} for i, line in enumerate(source.splitlines(), 1) if re.search(r"pytest\.(?:skip|mark\.(?:skip|xfail))|test\.(?:skip|fixme)|waitForTimeout|(?:asyncio\.|time\.)sleep\(", line)]
        count = len(bypath[name]) if framework in ("pytest", "Vitest", "Playwright") else None
        rows.append({"test_path": name, "framework": framework, "test_layer": layer, "feature": features(name), "ci_execution": ci, "collected_cases": count, "source_test_functions": len(pytests) if ispy else None, "runtime": runtimes.get(name), "dependencies": deps, "current_relevance": "Active" if ci.startswith("Yes") or ci.startswith("Indirect") else "Unknown; manual/conditional does not mean dead", "recommendation": "Keep; assess candidates in 01-test-suite-inventory.md", "imports": imports, "flags": flags})
    all_imports = {imp for row in rows for imp in row["imports"]}
    for row in rows:
        if row["test_path"].startswith("backend/evals/"):
            module = row["test_path"][8:-3].replace("/", ".")
            if any(imp == module or imp.startswith(module + ".") for imp in all_imports):
                row["ci_execution"] = "Indirect: imported by pytest; no direct CLI step"
                row["current_relevance"] = "Active"
        candidate_ids = []
        name = row["test_path"]
        if any("database" in item.get("fixtures", []) and "postgres" not in item.get("markers", []) for item in bypath[name]):
            candidate_ids.append("C01")
        if any(imp.startswith("tests.test_") for imp in row["imports"]):
            candidate_ids.append("C02")
        if name in {"frontend/tests/e2e/merge-readiness.spec.ts", "frontend/tests/e2e/ux-redesign.spec.ts", "frontend/tests/e2e/real.spec.ts"}:
            candidate_ids.append("C03")
        if name.endswith("onboarding-compatibility.spec.ts"):
            candidate_ids.append("C05")
        if name.endswith(("test_collaboration_load.py", "test_v3_load.py", "test_v3_live_eval.py")) or "/tests/live/" in name:
            candidate_ids.append("C06")
        if name == "frontend/tests/fullstack/v3.spec.ts":
            candidate_ids.append("C08")
        row["candidate_ids"] = candidate_ids
        if any(c in candidate_ids for c in ("C01", "C02", "C03")):
            row["recommendation"] = "Refactor setup/metadata; preserve assertions (" + ", ".join(candidate_ids) + ")"
        elif candidate_ids:
            row["recommendation"] = "Keep; review purpose/guard/root cause (" + ", ".join(candidate_ids) + ")"
    return {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "method": "git tracked files; AST/source heuristics + real collector evidence; null runtime means not measured; no deletion inferred", "summary": {"rows": len(rows), "files_by_framework": dict(sorted(Counter(r["framework"] for r in rows).items())), "collected_by_framework": {k: sum(r["collected_cases"] or 0 for r in rows if r["framework"] == k) for k in sorted({r["framework"] for r in rows})}}, "exact_python_body_duplicate_groups": [items for items in hashes.values() if len(items) > 1], "tests": rows, "python_test_functions": functions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence", help="Input collector snapshots, independent of output directory")
    args = parser.parse_args()
    EVIDENCE = args.evidence_dir.resolve()
    for required in ("pytest-manifest.json", "vitest-collection.json", "playwright-e2e-collection.json", "playwright-fullstack-collection.json"):
        if not (EVIDENCE / required).is_file():
            parser.error(f"Missing required collector input: {EVIDENCE / required}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = build()
    (args.output_dir / "test-inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    columns = ("test_path", "framework", "test_layer", "feature", "ci_execution", "collected_cases", "source_test_functions", "runtime", "dependencies", "current_relevance", "recommendation")
    with (args.output_dir / "test-inventory.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in result["tests"]:
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], (dict, list)) else row[k] for k in columns})
    print(json.dumps(result["summary"], indent=2))
