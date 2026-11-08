"""Live-test plumbing: import path for the private helpers and a result file for the report."""

import json
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

RESULTS: list[dict[str, Any]] = []
RESULT_DIR = Path(__file__).resolve().parents[2] / "evals" / "results"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        RESULTS.append(
            {
                "test": item.name,
                "outcome": report.outcome,
                "duration_ms": int(report.duration * 1000),
                "properties": dict(report.user_properties),
            }
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    ran = [r for r in RESULTS if r["outcome"] in ("passed", "failed")]
    if not ran:
        return
    try:
        from _live import open_ledger

        ledger = open_ledger()
        totals: dict[str, Any] = {
            "calls": ledger.reserved_calls,
            "unknown_calls": ledger.unknown_calls,
            "spent_tokens": ledger.spent_tokens,
            "committed_usd": round(ledger.committed_usd, 6),
            "max_usd": ledger.budget.max_usd,
            "prices_verified_on": ledger.budget.prices.verified_on,
        }
    except Exception:  # the ledger summary is informational; never hide the test results
        totals = {}
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC)
    path = RESULT_DIR / f"live-compat-{stamp.date().isoformat()}.json"
    previous: list[Any] = []
    if path.is_file():
        previous = json.loads(path.read_text(encoding="utf-8")).get("runs", [])
    previous.append(
        {
            "at": stamp.isoformat(),
            "model": "gpt-6-luna",
            "openai_agents": version("openai-agents"),
            "openai": version("openai"),
            "results": ran,
            "ledger_after_run": totals,
        }
    )
    path.write_text(json.dumps({"runs": previous}, ensure_ascii=False, indent=2), encoding="utf-8")
