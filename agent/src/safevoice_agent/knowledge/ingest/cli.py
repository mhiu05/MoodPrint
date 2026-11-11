"""Offline ingestion commands. Live Voyage calls require an owner budget file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from safevoice_agent.knowledge.ingest.budget import BudgetBlocked
from safevoice_agent.knowledge.ingest.build import build_corpus
from safevoice_agent.knowledge.ingest.manifest import load_manifest
from safevoice_agent.knowledge.ingest.topics import PUBLISHABLE


def plan(manifest_path: Path) -> int:
    manifest, digest = load_manifest(manifest_path)
    counts: dict[str, int] = {}
    for source in manifest.sources:
        counts[source.licence_class] = counts.get(source.licence_class, 0) + 1
    usable = [
        source.source_id for source in manifest.sources if source.licence_class in PUBLISHABLE
    ]
    summary = {
        "manifest_sha256": digest,
        "sources": len(manifest.sources),
        "by_licence": counts,
        "usable_sources": usable,
        "documents": len(manifest.documents),
        "exclusions": len(manifest.exclusions),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="safevoice_agent.knowledge.ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    planned = sub.add_parser("plan")
    planned.add_argument("--manifest", type=Path, required=True)
    built = sub.add_parser("build")
    built.add_argument("--manifest", type=Path, required=True)
    built.add_argument("--out", type=Path, required=True)
    for name in (
        "acquire",
        "embed",
        "store",
        "validate",
        "publish",
        "rollback",
        "status",
        "verify-citations",
        "seed-synthetic",
    ):
        command = sub.add_parser(name)
        command.add_argument("--manifest", type=Path)
        command.add_argument("--build", type=Path)
        command.add_argument("--out", type=Path)
        command.add_argument("--target")
        command.add_argument("--version")
        command.add_argument("--to")
        command.add_argument("--embedder", choices=("hashing", "voyage"))
        command.add_argument(
            "--embedding-input",
            choices=("context", "context_folded"),
            default="context",
            help="what the document embedder sees: title+heading+text, optionally with the "
            "accent-stripped form appended",
        )
        command.add_argument("--budget-tokens", type=int)
        command.add_argument("--offline", action="store_true")
        command.add_argument("--link-check", action="store_true")
        command.add_argument("--only")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 1
    try:
        if args.command == "plan":
            return plan(args.manifest)
        if args.command == "build":
            report = build_corpus(args.manifest, args.out)
            print(json.dumps({"documents": report["documents"], "chunks": report["chunks"]}))
            return 0
        if args.command == "seed-synthetic":
            from safevoice_agent.knowledge.ingest.runtime import seed_synthetic

            return seed_synthetic(args.target or "test-env")
        from safevoice_agent.knowledge.ingest.runtime import dispatch

        return dispatch(args)
    except BudgetBlocked as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
