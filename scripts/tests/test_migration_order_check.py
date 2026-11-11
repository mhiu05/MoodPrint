"""Permutations change copied filenames only; cleanup survives command failures."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "migration_order", ROOT / "scripts/dev/migration_order_check.py"
)
assert SPEC and SPEC.loader
order = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(order)


def write_migrations(path):
    path.mkdir(parents=True)
    fixtures = {
        "20261107100631_f0_base.sql": b"-- baseline\r\nselect 1;\r\n",
        "20261107124427_f1_domain.sql": b"-- domain\nselect 2;\n",
        "20261108100000_ag_first.sql": b"-- ag first\n",
        "20261108100001_kb_first.sql": b"-- kb first\n",
        "20261108100002_ag_second.sql": b"-- ag second\n",
        "20261108100003_kb_second.sql": b"-- kb second\n",
    }
    for name, content in fixtures.items():
        (path / name).write_bytes(content)
    return fixtures


@pytest.mark.parametrize(
    "first,expected",
    [
        ("kb", ["f0", "f1", "kb", "kb", "ag", "ag"]),
        ("ag", ["f0", "f1", "ag", "ag", "kb", "kb"]),
    ],
)
def test_permutations_keep_baseline_chronology_phase_order_and_bytes(tmp_path, first, expected):
    source = tmp_path / "source"
    original = write_migrations(source)
    plan = order.permutation(source, first)
    assert [name.split("_")[1] for name, content in plan] == expected
    assert plan[:2] == list(original.items())[:2]
    assert [content for name, content in plan if "_kb_" in name] == [
        b"-- kb first\n",
        b"-- kb second\n",
    ]
    assert [content for name, content in plan if "_ag_" in name] == [
        b"-- ag first\n",
        b"-- ag second\n",
    ]
    assert len({name[:14] for name, content in plan}) == 6
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original


@pytest.mark.parametrize(
    "bad",
    [
        "20261108100000_kb_duplicate.sql",
        "20260230010000_kb_invalid_date.sql",
        "20261108250000_kb_invalid_hour.sql",
        "2026110810_kb_short.sql",
        "20261108100009_other_unknown.sql",
    ],
)
def test_invalid_or_duplicate_versions_are_rejected(tmp_path, bad):
    source = tmp_path / "source"
    write_migrations(source)
    (source / bad).write_text("select 1;")
    with pytest.raises(ValueError):
        order.permutation(source, "kb")


def test_baseline_only_is_valid_and_never_retimestamped(tmp_path):
    (tmp_path / "20261107100631_f0_base.sql").write_bytes(b"baseline")
    assert order.permutation(tmp_path, "kb") == [("20261107100631_f0_base.sql", b"baseline")]


@pytest.mark.parametrize("failure_call", [None, 1, 2, 3, 4, 5])
def test_stack_files_restore_on_reset_or_test_failure(tmp_path, failure_call):
    source = tmp_path / "supabase/migrations"
    original = write_migrations(source)
    stack = tmp_path / ".local/stacks/unit"
    target = stack / "supabase/migrations"
    target.mkdir(parents=True)
    (target / "stale.sql").write_bytes(b"stale copy")
    calls = []

    def run(workdir, *args):
        assert workdir == stack
        calls.append(args)
        if len(calls) == failure_call:
            return subprocess.CompletedProcess(args, 1, "secret must not leak", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    if failure_call:
        with pytest.raises(RuntimeError, match="failed") as caught:
            order.run_orders(source, stack, run)
        assert "secret" not in str(caught.value)
    else:
        order.run_orders(source, stack, run)
        assert calls == [("db", "reset", "--local", "--yes"), ("test", "db", "--local")] * 2 + [
            ("db", "reset", "--local", "--yes")
        ]
    assert {p.name: p.read_bytes() for p in target.iterdir()} == original
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original
    assert calls[-1] == ("db", "reset", "--local", "--yes")


def test_restores_source_copies_even_when_cli_raises(tmp_path):
    source = tmp_path / "supabase/migrations"
    original = write_migrations(source)
    stack = tmp_path / ".local/stacks/unit"
    (stack / "supabase/migrations").mkdir(parents=True)
    calls = []

    def run(workdir, *args):
        calls.append(args)
        if len(calls) == 1:
            raise OSError("synthetic interruption")
        return subprocess.CompletedProcess(args, 0, "", "")

    with pytest.raises(OSError):
        order.run_orders(source, stack, run)
    assert {p.name: p.read_bytes() for p in (stack / "supabase/migrations").iterdir()} == original
    assert len(calls) == 2


def test_rejects_source_or_arbitrary_target_before_mutation(tmp_path):
    source = tmp_path / "supabase/migrations"
    original = write_migrations(source)
    for workdir in [tmp_path, tmp_path / "other"]:
        with pytest.raises(ValueError):
            order.run_orders(source, workdir, lambda *args: pytest.fail("must not invoke CLI"))
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original


def test_current_stack_requires_existing_matching_config(tmp_path):
    stack = tmp_path / ".local/stacks/unit"
    (stack / "supabase").mkdir(parents=True)
    (stack / "supabase/config.toml").write_text(
        'project_id = "safevoice-unit"\n[db]\nport = 54622\n'
    )
    assert (
        order.current_stack(
            tmp_path, {"SAFEVOICE_STACK_NAME": "unit", "SAFEVOICE_PORT_OFFSET": "300"}
        )
        == stack
    )
    for env in [
        {},
        {"SAFEVOICE_STACK_NAME": "../escape", "SAFEVOICE_PORT_OFFSET": "300"},
        {"SAFEVOICE_STACK_NAME": "unit", "SAFEVOICE_PORT_OFFSET": "0"},
    ]:
        with pytest.raises(ValueError):
            order.current_stack(tmp_path, env)


def test_concurrent_order_check_cannot_mutate_or_reset_owned_stack(tmp_path):
    source = tmp_path / "supabase/migrations"
    write_migrations(source)
    stack = tmp_path / ".local/stacks/unit"
    (stack / "supabase/migrations").mkdir(parents=True)
    (stack / ".migration-order.lock").mkdir()
    (stack / "supabase/migrations/original.sql").write_bytes(b"owned")
    with pytest.raises(ValueError, match="owns"):
        order.run_orders(source, stack, lambda *args: pytest.fail("must not reset"))
    assert (stack / "supabase/migrations/original.sql").read_bytes() == b"owned"


def test_selected_order_still_restores_and_resets_source_chronology(tmp_path):
    source = tmp_path / "supabase/migrations"
    original = write_migrations(source)
    stack = tmp_path / ".local/stacks/unit"
    (stack / "supabase/migrations").mkdir(parents=True)
    calls = []

    def run(workdir, *args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    order.run_orders(source, stack, run, only_order="ag")
    assert calls == [
        ("db", "reset", "--local", "--yes"),
        ("test", "db", "--local"),
        ("db", "reset", "--local", "--yes"),
    ]
    assert {p.name: p.read_bytes() for p in (stack / "supabase/migrations").iterdir()} == original
