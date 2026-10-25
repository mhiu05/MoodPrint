"""Explicit opt-in: bounded real providers, disposable local DB and synthetic Auth only."""

import argparse
from pathlib import Path

from test_fullstack import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-env", type=Path, required=True)
    parser.add_argument("--allow-live-openai", action="store_true")
    parser.add_argument("--allow-live-voyage", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only this disposable smoke DB after a partial run",
    )
    parser.add_argument(
        "--model-request-limit", type=int, choices=range(1, 9), default=8
    )
    parser.add_argument(
        "--voyage-request-limit", type=int, choices=range(1, 5), default=4
    )
    args = parser.parse_args()
    if not args.allow_live_openai:
        parser.error(
            "--allow-live-openai is required (at most 8 model requests, 1200 output tokens each)"
        )
    if not args.provider_env.is_file():
        parser.error("Provider environment file is missing; no credentials are printed")
    return run(
        ["--reporter=list", "--output=.cache/local-mvp/provider"],
        server_module="tests.local_provider_server",
        playwright_config="playwright.provider.config.ts",
        extra_environment={
            "MOODPRINT_PROVIDER_ENV": str(args.provider_env.resolve()),
            "MOODPRINT_ALLOW_LIVE_OPENAI": "true",
            "MOODPRINT_ALLOW_LIVE_VOYAGE": str(args.allow_live_voyage).lower(),
            "MOODPRINT_SMOKE_RESUME": str(args.resume).lower(),
            "MOODPRINT_SMOKE_OPENAI_LIMIT": str(args.model_request_limit),
            "MOODPRINT_SMOKE_VOYAGE_LIMIT": str(args.voyage_request_limit),
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
