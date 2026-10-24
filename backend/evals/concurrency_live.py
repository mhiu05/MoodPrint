"""Bounded live concurrency probe: N synthetic users send one real turn at the same time.

Measures real provider latency/failures under the production admission limits. N is
capped at 12; this is a rate/latency probe, not a load test of paid calls.
"""

import argparse
import asyncio
import json
import os
import statistics
from pathlib import Path

from dotenv import dotenv_values

from app.core.config import Settings
from evals.scenarios_live import (
    ROOT,
    Recorder,
    build_app,
    client_for,
    consent,
    make_user,
    open_chat,
    prepare_database,
    send,
)

PROMPTS = [
    "Hôm nay mình thấy hơi căng thẳng vì bài tập.",
    "Gợi ý cho mình một cách thư giãn ngắn trước khi ngủ.",
    "Mình muốn tập thói quen đọc sách, bắt đầu thế nào?",
    "Cuối tuần này mình nên làm gì để nạp lại năng lượng?",
]


async def run(levels: list[int], force_ipv4: bool) -> dict:
    env = dotenv_values(ROOT / ".env")
    url = os.environ["TEST_DATABASE_URL"]
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        ai_enabled=True,
        openai_api_key=env["OPENAI_API_KEY"],
        openai_model=env.get("OPENAI_MODEL") or "gpt-6-luna",
        provider_force_ipv4=force_ipv4,
    )
    engine = await prepare_database(url)
    recorder = Recorder()
    app = build_app(engine, settings, recorder)
    report: dict = {
        "model": settings.openai_model,
        "syntheticOnly": True,
        "providerForceIpv4": force_ipv4,
        "levels": [],
    }
    try:
        for level in levels:
            users = [await make_user(app, f"Load {i}") for i in range(level)]
            clients = [client_for(app, user) for user in users]
            chats = []
            for client in clients:
                await consent(client, "AI", True)
                chats.append(await open_chat(client, "may"))
            recorder.scenario = f"n{level}"
            started = asyncio.get_running_loop().time()
            results = await asyncio.gather(
                *(
                    send(client, chat, PROMPTS[i % len(PROMPTS)])
                    for i, (client, chat) in enumerate(zip(clients, chats, strict=True))
                )
            )
            wall = (asyncio.get_running_loop().time() - started) * 1000
            done = [r["ms"] for r in results if r["status"] == "completed"]
            report["levels"].append(
                {
                    "concurrentUsers": level,
                    "completed": len(done),
                    "failed": [r["status"] for r in results if r["status"] != "completed"],
                    "latencyMs": {
                        "p50": round(statistics.median(done)),
                        "p95": round(sorted(done)[int(0.95 * (len(done) - 1))]),
                        "max": max(done),
                    }
                    if done
                    else None,
                    "wallMs": round(wall),
                    "usage": recorder.totals(f"n{level}"),
                }
            )
            for client in clients:
                await client.aclose()
    finally:
        await app.state.ai.close()
        await engine.dispose()
    report["status"] = (
        "PASS" if all(not level["failed"] for level in report["levels"]) else "FAIL"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--levels", type=int, nargs="+", default=[5, 10])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force-ipv4", action="store_true")
    args = parser.parse_args()
    if any(level < 1 or level > 12 for level in args.levels):
        parser.error("Levels are capped at 12 concurrent real calls")
    if args.output.exists():
        parser.error("Refusing to overwrite existing evidence")
    report = asyncio.run(run(args.levels, args.force_ipv4), loop_factory=asyncio.SelectorEventLoop)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
