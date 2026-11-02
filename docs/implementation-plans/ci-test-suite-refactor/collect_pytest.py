"""Collect real pytest node IDs/fixture closure. No test bodies or DB fixtures execute.

Run with the backend interpreter, working directory backend; --output is explicit.
"""
import argparse
import json
from pathlib import Path

import pytest


class Manifest:
    def __init__(self):
        self.items = []

    def pytest_collection_finish(self, session):
        for item in session.items:
            self.items.append({
                "nodeid": item.nodeid,
                "path": "backend/" + item.nodeid.split("::")[0].replace("\\", "/"),
                "markers": sorted({mark.name for mark in item.iter_markers()}),
                "fixtures": sorted(item.fixturenames),
            })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = Manifest()
    code = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider"], plugins=[manifest])
    args.output.write_text(json.dumps({"exit_code": int(code), "items": manifest.items}, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(code)
