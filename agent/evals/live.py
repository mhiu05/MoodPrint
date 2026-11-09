"""Shared plumbing for paid tests: key loading, budget gate and a metered OpenAI client.

Every request goes through ``GuardedTransport``. Nothing here prints or stores the key.
"""

import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
from evals.budget import (
    DEFAULT_BUDGET_PATH,
    BudgetError,
    BudgetLedger,
    GuardedTransport,
    load_budget,
)
from moodprint_shared.config import AppConfig
from openai import AsyncOpenAI

SCOPE = "phase3-live-compat"
EVAL_SCOPE = "phase3-eval"


def api_key() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    env_live = Path(".env.live")
    if env_live.is_file():  # only the single key we need; nothing else is read or kept
        for line in env_live.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def open_ledger(scope: str = SCOPE) -> BudgetLedger:
    """Raises ``BudgetError`` when the owner's budget is missing, expired or out of scope."""
    path = Path(os.environ.get("MOODPRINT_EVAL_BUDGET", DEFAULT_BUDGET_PATH))
    ledger = BudgetLedger(load_budget(path, scope=scope))
    if api_key() is None:
        raise BudgetError("OPENAI_API_KEY is not set")
    return ledger


def metered_client(
    ledger: BudgetLedger, label: str, timeout: float = 90
) -> tuple[AsyncOpenAI, httpx.AsyncClient]:
    http = httpx.AsyncClient(
        transport=GuardedTransport(
            httpx.AsyncHTTPTransport(), ledger, run_id=f"{label}-{uuid4().hex[:8]}"
        ),
        timeout=timeout,
    )
    # max_retries=0: a retry would be a second paid request the caller did not decide on.
    return AsyncOpenAI(api_key=api_key(), max_retries=0, http_client=http), http


def live_cfg(ledger: BudgetLedger) -> AppConfig:
    cap = ledger.budget.max_output_tokens_per_request
    base = AppConfig()
    return replace(
        base, agent=replace(base.agent, max_output_tokens=min(base.agent.max_output_tokens, cap))
    )
