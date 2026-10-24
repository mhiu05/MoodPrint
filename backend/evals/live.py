"""Finite, opt-in synthetic evaluation using the application's real provider adapter."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from app.ai.prompts import instructions, prompt_version
from app.ai.provider import SdkProvider
from app.ai.usage import UsageEvent
from app.core.config import Settings
from evals.dataset import VERSION, cases


def selected_cases(splits: list[str]) -> list[dict]:
    if not splits or set(splits) - {"calibration", "development", "heldout"}:
        raise ValueError("Choose explicit valid evaluation splits")
    return [case for case in cases() if case["split"] in splits]


def summarize_usage(events: list[UsageEvent]) -> dict:
    started = sum(e.kind == "request_started" for e in events)
    received = sum(e.kind == "response_received" for e in events)
    return {
        "requests_started": started,
        "responses_received": received,
        "unknown_usage_requests": max(0, started - received),
        "input_tokens": sum(e.input_tokens for e in events),
        "cached_input_tokens": sum(e.cached_input_tokens for e in events),
        "output_tokens": sum(e.output_tokens for e in events),
    }


async def no_progress():
    pass


async def evaluate(variants: list[str], splits: list[str], output: Path, concurrency: int = 3):
    if await asyncio.to_thread(output.exists):
        raise ValueError("Refusing to overwrite evaluation evidence; choose a new output path")
    if not 1 <= concurrency <= 5:
        raise ValueError("Concurrency must be between one and five")
    for variant in variants:
        prompt_version(variant)
    selected = selected_cases(splits)
    settings = Settings().model_copy(update={"ai_enabled": True})
    if not settings.openai_api_key.get_secret_value() or not settings.openai_model:
        raise ValueError("Configure the real provider locally; no fake fallback exists")
    report = {
        "kind": "real-provider-evaluation", "synthetic": True,
        "created_at": datetime.now(UTC).isoformat(), "dataset_version": VERSION,
        "sdk": importlib.metadata.version("openai-agents"),
        "model": settings.openai_model, "splits": splits,
        "configuration": {"max_output_tokens": 1200, "max_turns": 3, "timeout": 30,
                          "retries": 0, "store": False, "tracing": False},
        "tool_scope": "No tools exposed; production tools tested separately through authorized domain runtime",
        "rows": [],
    }
    await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    writer = asyncio.Lock()

    async def run(case, variant):
        async with semaphore:
            events: list[UsageEvent] = []

            async def observe(event):
                events.append(event)

            row = {
                "caseId": case["id"], "botId": case["botId"], "split": case["split"],
                "category": case["category"], "prompt": case["prompt"], "synthetic": True,
                "variant": variant, "promptVersion": prompt_version(variant),
                "promptSha256": hashlib.sha256(instructions(case["botId"], variant).encode()).hexdigest(),
                "model": settings.openai_model,
            }
            start = time.perf_counter()
            try:
                result = await SdkProvider(settings, usage_observer=observe, prompt_variant=variant).run(
                    bot_id=case["botId"], history=[{"role": "user", "content": case["prompt"]}],
                    tools=[], context=None, on_progress=no_progress,
                )
                row.update(status="PASS", output=result.model_dump(mode="json"))
            except Exception as error:
                # No exception messages, headers, request bodies or provider credentials in artifacts.
                row.update(status="FAILED", error_type=type(error).__name__,
                           http_status=getattr(error, "status_code", None))
            row.update(latency_seconds=round(time.perf_counter() - start, 3),
                       usage=summarize_usage(events),
                       tools=[e.tool_name for e in events if e.kind == "tool_started"])
            async with writer:
                report["rows"].append(row)
                await asyncio.to_thread(output.write_text, json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"done": len(report["rows"]), "variant": variant,
                              "caseId": case["id"], "status": row["status"]}), flush=True)

    # Interleave variants for each case to reduce temporal differences.
    await asyncio.gather(*(run(case, variant) for case in selected for variant in variants))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--variants", nargs="+", choices=["baseline", "A", "B"], required=True)
    parser.add_argument("--splits", nargs="+", default=["calibration", "development"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Do not echo SDK exception bodies into console logs.
    report = asyncio.run(evaluate(args.variants, args.splits, args.output, args.concurrency))
    return int(any(row["status"] != "PASS" for row in report["rows"]))


if __name__ == "__main__":
    raise SystemExit(main())
