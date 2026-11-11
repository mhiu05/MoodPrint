"""The manifest digest must not depend on the checkout's line endings (Windows CRLF vs Linux LF)."""

from __future__ import annotations

import shutil
from pathlib import Path

from safevoice_agent.knowledge.ingest.manifest import load_manifest

CORPUS = Path(__file__).resolve().parents[2] / "ingestion" / "corpus"


def _copy_with_line_endings(target: Path, newline: bytes) -> Path:
    shutil.copytree(CORPUS.parent / "authored", target / "authored")
    shutil.copytree(CORPUS.parent / "legal", target / "legal")
    shutil.copytree(CORPUS, target / "corpus")
    for path in target.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".toml"}:
            data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
            path.write_bytes(data)
    return target / "corpus" / "manifest.toml"


def test_manifest_digest_ignores_line_endings(tmp_path: Path) -> None:
    lf = _copy_with_line_endings(tmp_path / "lf", b"\n")
    crlf = _copy_with_line_endings(tmp_path / "crlf", b"\r\n")
    _, lf_digest = load_manifest(lf)
    _, crlf_digest = load_manifest(crlf)
    assert lf_digest == crlf_digest
