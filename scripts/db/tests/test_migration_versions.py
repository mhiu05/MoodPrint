"""Hosted deployment must reject version collisions and history drift."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "migration_safety", Path(__file__).parents[1] / "safety.py"
)
assert SPEC and SPEC.loader
safety = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(safety)


@pytest.mark.parametrize(
    "names",
    [
        ["20261108100000_kb_one.sql", "20261108100000_ag_two.sql"],
        ["20260230010000_kb_bad.sql"],
        ["20261108240000_ag_bad.sql"],
        ["20261108100000_other_bad.sql"],
        ["123_f0_bad.sql"],
        ["20261108100000_kb_Bad.sql"],
    ],
)
def test_invalid_local_migration_versions_are_rejected(names):
    with pytest.raises(ValueError):
        safety.check_history([Path(name) for name in names], [])


@pytest.mark.parametrize(
    "history",
    [
        [("20261108100000", "kb_one"), ("20261108100000", "kb_one")],
        [("20261108100001", "ag_two"), ("20261108100000", "kb_one")],
        [("20261108100000", "wrong_name")],
        [("20261108100002", "unknown")],
    ],
)
def test_duplicate_disordered_or_unknown_applied_history_is_rejected(history):
    with pytest.raises(ValueError):
        safety.check_history(
            [Path("20261108100000_kb_one.sql"), Path("20261108100001_ag_two.sql")], history
        )


def test_interleaved_phases_return_pending_in_timestamp_order():
    paths = [
        Path("20261108100002_kb_three.sql"),
        Path("20261108100000_kb_one.sql"),
        Path("20261108100001_ag_two.sql"),
    ]
    assert safety.check_history(paths, [("20261108100001", "ag_two")]) == [
        Path("20261108100000_kb_one.sql"),
        Path("20261108100002_kb_three.sql"),
    ]
