"""KnowledgeConfig defaults must match the configuration locked on the dev split (U-KB-40)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from moodprint_shared.config import KnowledgeConfig

LOCKED = Path(__file__).resolve().parents[2] / "evals" / "knowledge" / "results"


def test_defaults_equal_the_locked_dev_configuration() -> None:
    locked = json.loads((LOCKED / "locked-config-v2.json").read_text(encoding="utf-8"))
    actual = asdict(KnowledgeConfig())
    for key, value in locked["config"].items():
        assert actual[key] == value, key


def test_the_lock_names_the_split_and_the_frozen_benchmark() -> None:
    locked = json.loads((LOCKED / "locked-config-v2.json").read_text(encoding="utf-8"))
    assert locked["split_used"] == "dev only"
    assert len(locked["benchmark_sha256_lf"]) == 64
    assert locked["not_met_on_dev"], "unmet targets must stay on the record"
