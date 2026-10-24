"""Rebuild metrics from saved synthetic evidence without making provider requests."""

import argparse
import json
import math
import statistics
from pathlib import Path

from app.ai.prompts import SELECTED_VARIANTS, VERSIONS
from app.ai.schemas import AiOutput

WEIGHTS = {"intent_usefulness": .25, "natural_persona": .20, "grounding": .20,
           "context_memory": .15, "tool_action": .15, "clarity": .05}


def rebuild(directory: Path):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    def score(row):
        return sum(row[key] * weight for key, weight in WEIGHTS.items())

    def mean(rows):
        return round(statistics.mean(score(row) for row in rows), 4)

    dev, held = read("development-judge.json"), read("heldout-judge.json")
    comparison = {"rubric_weights": WEIGHTS, "selection_frozen_before_heldout": True,
                  "reviewers": "Same-model blinded judge plus primary agent manual review; no independent humans",
                  "bots": [], "hard_gate_failures_in_judge": 0}
    for bot, variant in SELECTED_VARIANTS.items():
        row = {"bot_id": bot, "selected_variant": variant, "before_version": VERSIONS["baseline"], "after_version": VERSIONS[variant]}
        for split, report in (("development_and_calibration", dev), ("heldout", held)):
            rows = [x for x in report["rows"] if x.get("botId") == bot and not x["repeat"]]
            row[split] = {"cases": len(rows) // 3,
                          **{v: mean([x for x in rows if x["variant"] == v]) for v in ("baseline", "A", "B")}}
            row[split]["selected"] = row[split][variant]
            row[split]["delta"] = round(row[split][variant] - row[split]["baseline"], 4)
        comparison["bots"].append(row)
    comparison["heldout_overall"] = {
        "baseline": mean([x for x in held["rows"] if not x["repeat"] and x["variant"] == "baseline"]),
        "selected": mean([x for x in held["rows"] if not x["repeat"] and x["variant"] == SELECTED_VARIANTS[x["botId"]]]),
        "sample_size": 20,
    }
    repeats = [x for x in dev["rows"] if x["repeat"]]
    comparison["judge_order_repeat_mean_abs_difference"] = round(statistics.mean(abs(score(x) - score(next(y for y in dev["rows"] if y["caseId"] == x["caseId"] and y["variant"] == x["variant"] and not y["repeat"]))) for x in repeats), 4)
    comparison["hard_gate_failures_in_judge"] = sum(bool(x.get("hard_gate_failure")) for x in dev["rows"] + held["rows"])

    metrics = {"model": "gpt-6-luna", "sdk": "0.24.0", "openai_sdk": "3.37.0", "parts": {}}
    rows = []
    for name in ("baseline-results.json", "candidate-results.json", "heldout-results.json"):
        batch = read(name)["rows"]
        rows.extend(batch)
        usage = {key: sum(row["usage"].get(key, 0) for row in batch) for key in (
            "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens",
        )}
        latency = sorted(row["latency_seconds"] for row in batch)
        metrics["parts"][name] = {**usage, "cases": len(batch), "errors": sum(row["status"] != "PASS" for row in batch),
                                  "latency_p50_seconds": statistics.median(latency), "latency_p95_seconds": latency[math.ceil(.95 * len(latency)) - 1]}
    for name in ("smoke-results.json", "timeout-results.json"):
        metrics["parts"][name] = read(name)["usage"]
    for name, report in (("development-judge.json", dev), ("heldout-judge.json", held)):
        usage = report["usage"]
        receipts = len({(x["caseId"], x["repeat"]) for x in report["rows"] if "variant" in x})
        metrics["parts"][name] = {"requests_started": usage["requests"], "responses_received": receipts,
                                  **{k: usage[k] for k in ("input_tokens", "cached_input_tokens", "output_tokens")}}
    events = [json.loads(line) for line in (directory / "http-usage.jsonl").read_text().splitlines() if line]
    metrics["parts"]["authorized_http_browser"] = {
        "requests_started": sum(e["kind"] == "request_started" for e in events),
        "responses_received": sum(e["kind"] == "response_received" for e in events),
        **{k: sum(e[k] for e in events) for k in ("input_tokens", "cached_input_tokens", "output_tokens")},
        "tools_observed": sorted({e["tool_name"] for e in events if e["tool_name"]}),
    }
    metrics["text_totals"] = {k: sum(part.get(k, 0) for part in metrics["parts"].values()) for k in (
        "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens",
    )}
    totals = metrics["text_totals"]
    totals["unknown_usage_attempts"] = totals["requests_started"] - totals["responses_received"]
    totals["estimated_known_cost_usd"] = round(((totals["input_tokens"] - totals["cached_input_tokens"]) * .1
                                                 + totals["cached_input_tokens"] * .01 + totals["output_tokens"] * .5) / 1_000_000, 8)
    metrics.update(pricing_source="https://developers.openai.com/api/docs/pricing", pricing_date="2026-10-24",
                   cost_limitations="Estimate for known text receipts only; excludes unknown cancelled/timeout usage and audio charges. Not an invoice.",
                   audio_requests={"tts": 2, "stt": 2, "tts_token_usage": "not returned by binary speech response", "native_microphone": "BLOCKED: NotSupportedError", "synthetic_stream_stt_ui": "PASS"},
                   inference_attempts_including_audio=totals["requests_started"] + 4)
    for row in rows:
        AiOutput.model_validate(row["output"])
    comparison["structured_output_contracts"] = {"passed": len(rows), "failed": 0}
    for name, report in (("comparison-results.json", comparison), ("performance-usage.json", metrics)):
        (directory / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"heldout": comparison["heldout_overall"], "usage": metrics["text_totals"], "attempts_with_audio": metrics["inference_attempts_including_audio"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    rebuild(parser.parse_args().directory)
