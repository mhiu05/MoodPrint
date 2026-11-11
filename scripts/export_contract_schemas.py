"""Export the frozen shared JSON schemas (or fail when snapshots have drifted)."""

import argparse
import json
from pathlib import Path

from safevoice_shared.testing.schemas import contract_schemas


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / "shared/contract-schemas"
    expected = contract_schemas()
    if args.check:
        actual = {
            p.name: json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")
        }
        if actual != expected:
            print("Contract snapshots differ; review and export explicitly.")
            return 1
    else:
        directory.mkdir(parents=True, exist_ok=True)
        for filename, schema in expected.items():
            (directory / filename).write_text(
                json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
