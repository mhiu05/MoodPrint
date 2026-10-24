"""One synthetic real-provider attempt with an intentionally short application deadline."""

import asyncio
import json
import logging
from pathlib import Path

import app.ai.provider as adapter
from app.ai.usage import UsageEvent
from app.core.config import Settings
from evals.live import no_progress, summarize_usage


async def main():
    events: list[UsageEvent] = []
    async def observe(event):
        events.append(event)
    settings = Settings().model_copy(update={"ai_enabled": True})
    adapter.RUN_TIMEOUT_SECONDS = 0.3
    try:
        await adapter.SdkProvider(settings, usage_observer=observe).run(
            bot_id="may", history=[{"role": "user", "content": "Kể một câu chuyện tưởng tượng gồm mười đoạn về một chú mèo vẽ tranh."}],
            tools=[], context=None, on_progress=no_progress,
        )
        status = "UNEXPECTED_COMPLETION"
    except TimeoutError:
        status = "PASS"
    report = {"status": status, "synthetic": True, "deadline_seconds": 0.3,
              "usage": summarize_usage(events), "no_output_published": status == "PASS",
              "note": "Started attempts with no receipt have unknown provider billing; not zero-cost calls"}
    await asyncio.to_thread(Path("../docs/plans/validation-artifacts/live-ai/timeout-results.json").write_text,
                            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(main())
