"""Verify the tracked, hash-pinned SQL approvals that the Supabase scripts consume.

Read-only and offline: it never connects to a database or runs a subprocess. It fails when
a required approval is missing or altered by even one byte, when SQL appears in the pinned
directory without a manifest entry, when a consumer names a file the manifest does not
pin (or still points at the retired docs/ location), and when nothing is pinned at all.
Listing a file in the manifest records what was approved; it never authorises running it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DIRECTORY = "deploy/supabase/reviewed-sql"
MANIFEST = f"{DIRECTORY}/MANIFEST.json"
CONSUMERS = (
    "scripts/apply_supabase_review.py",
    "scripts/provision_supabase_runtime.py",
    "scripts/verify_migration_review.py",
    "scripts/prepare_supabase_migration.py",
)
# Written by prepare_supabase_migration.py under deploy/supabase/reports; never executed.
GENERATED = {"supabase-migrations-0001-0005.sql"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.sql$")
LITERAL = re.compile(r"""["']([^"'\s]*?\.sql)["']""")


def check(root: Path) -> dict:
    errors: list[str] = []
    pinned = root / DIRECTORY
    entries: dict[str, dict] = {}
    manifest_path = root / MANIFEST
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = None
        errors.append(f"Manifest missing: {MANIFEST}")
    except (OSError, ValueError) as error:
        data = None
        errors.append(f"Manifest unreadable: {MANIFEST} ({type(error).__name__})")
    if data is not None:
        if not isinstance(data, dict):
            errors.append("Manifest must be a JSON object")
            data = {}
        listed = data.get("artifacts")
        if data and data.get("version") != 1:
            errors.append("Manifest version must be 1")
        if not isinstance(listed, list) or not listed:
            errors.append("Manifest lists no artifacts (an empty set would pass nothing meaningful)")
            listed = []
        for entry in listed:
            name = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(name, str) or not NAME.fullmatch(name):
                errors.append(f"Manifest entry has an invalid path: {name!r}")
                continue
            if name in entries:
                errors.append(f"Duplicate manifest entry: {name}")
                continue
            entries[name] = entry

    for name, entry in sorted(entries.items()):
        path = pinned / name
        if path.is_symlink() or not path.is_file():
            errors.append(f"Approved file missing: {DIRECTORY}/{name}")
            continue
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != str(entry.get("sha256", "")).lower():
            errors.append(f"{name}: SHA256 differs from the approved value (altered, or newlines converted)")
        elif entry.get("bytes") != len(content):
            errors.append(f"{name}: size differs from the manifest")

    if pinned.is_dir():
        for path in sorted(pinned.glob("*.sql")):
            if path.name not in entries:
                errors.append(f"{path.name}: SQL in {DIRECTORY} is not in the manifest (needs review and approval)")

    referenced: set[str] = set()
    for consumer in CONSUMERS:
        path = root / consumer
        if not path.is_file():
            errors.append(f"Consumer script missing: {consumer}")
            continue
        text = path.read_text(encoding="utf-8")
        for literal in LITERAL.findall(text):
            name = literal.rsplit("/", 1)[-1]
            if literal.startswith("docs/") or "/docs/" in literal:
                errors.append(f"{consumer}: {literal} points at the retired docs/ location")
            elif literal.startswith("backend/"):
                # Application source the approval is cross-checked against, not an approval.
                if not (root / literal).is_file():
                    errors.append(f"{consumer}: {literal} does not exist")
            elif name in GENERATED:
                continue
            elif name in entries:
                referenced.add(name)
            else:
                errors.append(f"{consumer}: {name} is not pinned by the manifest")
    for name in sorted(set(entries) - referenced):
        errors.append(f"{name}: no script consumes this approval (remove it or wire it up)")

    return {
        "status": "FAIL" if errors else "PASS",
        "scope": "Tracked approval integrity only; says nothing about hosted state or authorisation to apply",
        "artifactCount": len(entries),
        "referencedCount": len(referenced),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Print the complete report")
    args = parser.parse_args(argv)
    report = check(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['status']}: {report['artifactCount']} pinned approvals; {report['referencedCount']} consumed by scripts")
        for error in report["errors"]:
            print(f"ERROR: {error}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
