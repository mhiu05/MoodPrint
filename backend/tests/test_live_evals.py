import pytest


def test_live_eval_split_selection_never_silently_includes_heldout():
    from evals.live import selected_cases

    rows = selected_cases(["calibration", "development"])
    assert len(rows) == 40
    assert {r["split"] for r in rows} == {"calibration", "development"}
    with pytest.raises(ValueError):
        selected_cases(["unknown"])


def test_versioned_variants_preserve_baseline_and_differ_by_strategy():
    from app.ai.prompts import instructions, prompt_version

    assert instructions("may", "baseline").startswith("Bạn là Mây. Lắng nghe ấm áp, hỏi ngắn")
    assert instructions("may", "A") != instructions("may", "B")
    assert prompt_version("baseline") != prompt_version("A") != prompt_version("B")
    with pytest.raises(ValueError):
        instructions("may", "unknown")


def test_usage_totals_keep_unknown_receipts_and_cached_pricing_separate():
    from app.ai.usage import UsageEvent
    from evals.live import summarize_usage

    report = summarize_usage([
        UsageEvent(kind="request_started"),
        UsageEvent(kind="response_received", input_tokens=100, cached_input_tokens=40, output_tokens=20),
        UsageEvent(kind="request_started"),
    ])
    assert report["requests_started"] == 2
    assert report["responses_received"] == 1
    assert report["unknown_usage_requests"] == 1
    assert report["input_tokens"] == 100
    assert report["cached_input_tokens"] == 40
