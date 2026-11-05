"""Allowlisted capacity diagnostics. Never serialize Settings or environment values wholesale."""

import math
import re

from app.core.config import Settings

CAPACITY_FIELDS = (
    "ai_global_concurrency", "ai_user_concurrency", "ai_requests_per_minute",
    "ai_timeout_seconds", "ai_daily_budget_usd", "ai_daily_turns_per_user",
    "ai_accounting_enabled", "database_pool_size", "database_pool_overflow",
    "ai_bounded_reservations_enabled", "ai_dispatch_gate_enabled", "ai_dispatch_queue_limit",
    "auth_nat_policy_enabled", "database_pool_metrics_enabled", "database_transaction_timeouts_enabled",
    "database_statement_timeout_ms", "database_lock_timeout_ms",
    "database_pool_timeout", "database_pool_mode", "proactive_worker_enabled",
    "proactive_worker_concurrency", "journal_auto_memory_enabled", "ai_collaboration_enabled",
    "ai_smart_orchestration_enabled", "ai_group_chat_enabled", "auth_captcha_enabled",
)


def ai_capacity_fingerprint(settings: Settings) -> dict:
    from app.ai.accounting import CAPPED_PRICING_VERSION
    from app.ai.envelope import BOUNDED_PRICING_VERSION

    result = {name: getattr(settings, name) for name in CAPACITY_FIELDS}
    # Model is user-configurable: only recognized public identifiers are safe diagnostics.
    result["openai_model"] = settings.openai_model if settings.openai_model == "gpt-6-luna" else "unverified"
    result["pricing_version"] = BOUNDED_PRICING_VERSION if settings.ai_bounded_reservations_enabled else CAPPED_PRICING_VERSION
    result["supported_api_processes"] = 1
    result["source"] = "resolved_settings"
    return result


def duplicate_capacity_keys(content: str) -> dict[str, list[int]]:
    """Only key names and line numbers; even malformed/duplicate secrets stay private."""
    allowed = {name.upper() for name in CAPACITY_FIELDS} | {"OPENAI_MODEL"}
    locations: dict[str, list[int]] = {}
    for line_number, line in enumerate(content.splitlines(), 1):
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and (name := match[1].upper()) in allowed:
            locations.setdefault(name, []).append(line_number)
    return {name: lines for name, lines in locations.items() if len(lines) > 1}


def shutdown_bounds(ai_timeout_seconds: float) -> dict[str, int]:
    # Group turns have the longest outer deadline: twice the single-turn budget.
    server = max(45, math.ceil(2 * ai_timeout_seconds + 10))
    return {"server_grace": server, "container_grace": server + 10}
