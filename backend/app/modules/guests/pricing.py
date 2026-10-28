"""Owner-approved prices and the daily budget, parsed fail-closed.

No price, model or budget is ever guessed: a missing, partial, non-numeric or non-positive value
means that kind of paid guest work is unavailable (never unlimited, never a fallback). The mapping
comes from the server-only ``GUEST_PRICING_JSON`` setting and carries no secret.

Expected shape (integers are nano-USD, i.e. 1e-9 USD)::

    {"ai":    {"pricing_version": "...", "input_nano_per_token": 1, "cached_nano_per_token": 1,
               "output_nano_per_token": 1, "max_input_tokens": 1},
     "voice": {"pricing_version": "...", "nano_per_second": 1, "quantum_seconds": 1},
     "embed": {"pricing_version": "...", "nano_per_request": 1}}
"""

from decimal import Decimal
from math import ceil, isfinite
from typing import Any

AI_REQUESTS = 3  # the SDK turn limit: one admitted turn may issue up to three model requests
AI_OUTPUT_TOKENS = 1200  # per-request output cap already enforced by the provider adapter
NANO = Decimal(1_000_000_000)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _section(raw: Any, *keys: str) -> dict[str, int] | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("pricing_version"), str):
        return None
    if not raw["pricing_version"]:
        return None
    values = {key: _positive_int(raw.get(key)) for key in keys}
    if any(value is None for value in values.values()):
        return None
    return {key: value for key, value in values.items() if value is not None}


def budget_nano(budget: Decimal | None) -> int | None:
    """Daily budget in nano-USD, or None when unset or zero (paid guest work stays closed)."""
    if budget is None:
        return None
    value = Decimal(str(budget))
    if value <= 0:
        return None
    return int(value * NANO)


def ai_upper(pricing: dict[str, Any]) -> tuple[str, int] | None:
    """Conservative reservation for one admitted turn: 3 * (max_input * max(rate) + 1200 * output)."""
    values = _section(
        pricing.get("ai"),
        "input_nano_per_token",
        "cached_nano_per_token",
        "output_nano_per_token",
        "max_input_tokens",
    )
    if values is None:
        return None
    per_request = (
        values["max_input_tokens"]
        * max(values["input_nano_per_token"], values["cached_nano_per_token"])
        + AI_OUTPUT_TOKENS * values["output_nano_per_token"]
    )
    return pricing["ai"]["pricing_version"], AI_REQUESTS * per_request


def voice_upper(pricing: dict[str, Any], seconds: float) -> tuple[str, int] | None:
    """Reserve the validated duration rounded UP to the provider billing quantum (max 30 s)."""
    values = _section(pricing.get("voice"), "nano_per_second", "quantum_seconds")
    if values is None or not isfinite(seconds) or seconds <= 0:
        return None
    quantum = values["quantum_seconds"]
    # Valid PCM durations preserve a sample well above float precision (<=30s,
    # <=48kHz). Round the original duration, never a truncated millisecond value.
    billed = ceil(seconds / quantum) * quantum
    return pricing["voice"]["pricing_version"], billed * values["nano_per_second"]


def embed_upper(pricing: dict[str, Any]) -> tuple[str, int] | None:
    values = _section(pricing.get("embed"), "nano_per_request")
    if values is None:
        return None
    return pricing["embed"]["pricing_version"], values["nano_per_request"]


def actual_ai_cost(pricing: dict[str, Any], input_tokens: int, cached_tokens: int, output_tokens: int) -> int | None:
    """Actual cost from observed usage, or None when it cannot be computed (charge the bound)."""
    values = _section(
        pricing.get("ai"),
        "input_nano_per_token",
        "cached_nano_per_token",
        "output_nano_per_token",
        "max_input_tokens",
    )
    if values is None or min(input_tokens, cached_tokens, output_tokens) < 0:
        return None
    fresh = max(0, input_tokens - cached_tokens)
    return (
        fresh * values["input_nano_per_token"]
        + cached_tokens * values["cached_nano_per_token"]
        + output_tokens * values["output_nano_per_token"]
    )


def kind_available(settings, kind: str) -> bool:
    """Paid guest work of this kind is open only with the flag, a positive budget and its prices."""
    if not settings.guest_paid_enabled or budget_nano(settings.guest_daily_budget_usd) is None:
        return False
    pricing = settings.guest_pricing_json
    if kind == "ai":
        return ai_upper(pricing) is not None
    if kind == "voice":
        return voice_upper(pricing, 1.0) is not None
    if kind == "embed":
        return embed_upper(pricing) is not None
    return False
