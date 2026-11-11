"""Dispatch future synthetic seed CLI; only an absent feature returns exit 2."""

import sys
from importlib.util import find_spec
from runpy import run_module


def main() -> int:
    module = "safevoice_agent.knowledge.ingest"
    if find_spec(module) is None:
        return 2
    sys.argv = [module, "seed-synthetic", "--target", "test-env"]
    run_module(module, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
