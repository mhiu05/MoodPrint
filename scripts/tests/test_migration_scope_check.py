"""Static scope checks reject ambiguous SQL instead of silently skipping it."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "migration_scope", ROOT / "scripts/dev/migration_scope_check.py"
)
assert SPEC and SPEC.loader
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


@pytest.mark.parametrize(
    "phase,sql",
    [
        (
            "kb",
            "create schema if not exists knowledge; create table knowledge.sources(id uuid); alter table knowledge.sources enable row level security;",
        ),
        (
            "kb",
            'create table "knowledge"."Sources" (id uuid, title text default \'app.secret\'); -- app.fake\n',
        ),
        (
            "kb",
            "/* outer /* nested app.bad */ comment */ create policy approved on knowledge.sources for select to authenticated using(true);",
        ),
        (
            "kb",
            "grant select on knowledge.sources to authenticated; revoke all on schema knowledge from anon;",
        ),
        (
            "kb",
            "create function knowledge.find() returns int language sql security invoker as $$ select count(*)::int from knowledge.sources; $$;",
        ),
        (
            "ag",
            "create table app.roleplay_sessions(id uuid references app.cases(id)); alter table app.roleplay_sessions enable row level security; create policy owner on app.roleplay_sessions using(true); grant select on app.roleplay_sessions to authenticated;",
        ),
        ("ag", "create index concurrently cases_extra_idx on app.cases(id);"),
    ],
)
def test_accepts_scoped_sql_without_treating_literals_comments_as_identifiers(phase, sql):
    scope.check_sql(sql, phase, {"app.cases", "app.messages"})


@pytest.mark.parametrize(
    "phase,sql",
    [
        ("kb", 'create table "app"."stolen"(id uuid);'),
        (
            "kb",
            "create table knowledge.ok(id int); alter table app.messages add column secret text;",
        ),
        ("kb", "create role ingestion;"),
        ("ag", 'alter /* hidden */ role "safevoice_api" superuser;'),
        ("kb", "grant authenticated to safevoice_api;"),
        ("kb", "drop table app.messages;"),
        ("ag", "alter table app.messages disable row level security;"),
        ("ag", 'alter table "app"."messages" add column x text;'),
        ("ag", "drop table app.messages;"),
        ("ag", "create index unsafe on app.cases(id);"),
        ("ag", "create policy leaked on app.messages using(true);"),
        ("ag", "create trigger leaked before insert on app.messages execute function app.evil();"),
        ("ag", "grant select on app.messages to anon;"),
        ("ag", "create table knowledge.nope(id int);"),
        ("kb", "create table knowledge.ok(id uuid references auth.users(id));"),
        ("kb", "drop schema knowledge cascade;"),
        ("kb", "truncate knowledge.sources;"),
        ("kb", "delete from knowledge.sources;"),
        ("kb", "update knowledge.sources set id=1;"),
        ("kb", "delete from knowledge.sources returning 'where';"),
        (
            "kb",
            "delete from knowledge.sources returning (select id from knowledge.sources where false);",
        ),
        ("kb", "do $$ begin execute 'drop table app.messages'; end $$;"),
        (
            "kb",
            "create function knowledge.bad() returns void language plpgsql as $x$ begin execute 'drop table app.messages'; end $x$;",
        ),
        (
            "kb",
            "create function knowledge.bad() returns int language sql as $$ select count(*) from app.messages; $$;",
        ),
        (
            "kb",
            "create function knowledge.bad() returns int language sql security definer as $$ select 1; $$;",
        ),
        (
            "kb",
            "create function knowledge.bad() returns void language sql as $$ alter role safevoice_api superuser; $$;",
        ),
        ("kb", "create table unqualified(id int);"),
        ("kb", "set search_path = app; create table sneaky(id int);"),
        ("kb", "create table knowledge.ok(id int); /* unterminated"),
        ("kb", 'create table "knowledge.ok(id int);'),
        ("kb", "create function knowledge.bad() returns int language sql as $$ select 1;"),
        ("kb", "create table knowledge.ok(id int); select set_config('role','postgres',false);"),
        ("kb", "create table knowledge.ok(id int); \\i /tmp/payload.sql"),
        ("ag", "alter table app.roleplay_sessions rename to messages;"),
        ("kb", "create extension if not exists unreviewed;"),
        ("ag", "create table app.fresh(id int); drop table app.fresh, app.messages;"),
        ("kb", "grant usage on schema knowledge, public to anon;"),
        (
            "kb",
            "create function knowledge.bad() returns int language sql as $$ select evil_side_effect(); $$;",
        ),
        (
            "kb",
            "create function knowledge.bad() returns int language sql as $$ select pg_terminate_backend(1); $$;",
        ),
        (
            "kb",
            "create function knowledge.bad() returns int language sql as $$ select 1 from unqualified; $$;",
        ),
        ("kb", "create table knowledge.ok(id bigint default nextval('app.seq'::regclass));"),
        (
            "kb",
            "create table knowledge.ok(id int); delete from knowledge.ok where exists(select 1 from app.messages);",
        ),
    ],
)
def test_rejects_out_of_scope_or_unsupported_statements(phase, sql):
    with pytest.raises(ValueError):
        scope.check_sql(sql, phase, {"app.cases", "app.messages"})


@pytest.mark.parametrize(
    "phase,sql",
    [
        ("ag", "CREATE TABLE app.phase_child () INHERITS (app.cases);"),
        ("ag", 'create table "app"."phase_child" () inherits ("app"."cases");'),
        ("ag", "create table app.phase_child () /* note */ InHeRiTs (app.cases);"),
        ("ag", "create table app.phase_child()inherits(app.cases);"),
        ("ag", "create table app.phase_child partition of app.cases;"),
        (
            "ag",
            "create table app.phase_child (id int) partition of app.cases for values in (1);",
        ),
        ("ag", 'create table "app"."phase_child" partition of "app"."cases";'),
        ("kb", "create table knowledge.child () inherits (knowledge.parent);"),
        ("kb", "create table knowledge.child partition of knowledge.parent;"),
    ],
)
def test_create_table_parent_attachment_is_rejected(phase, sql):
    with pytest.raises(ValueError, match="parent semantics"):
        scope.check_sql(sql, phase, {"app.cases", "app.messages"})


@pytest.mark.parametrize(
    "phase,sql",
    [
        ("ag", "create table app.phase_child (id int); -- inherits (app.cases)\n"),
        ("ag", "create table app.phase_child (label text default 'inherits (app.cases)');"),
        ("ag", "create table app.phase_child (inherits int);"),
        ("ag", "/* partition of app.cases */ create table app.phase_child (id int);"),
        (
            "kb",
            "create table knowledge.sources (note text default 'partition of knowledge.parent');",
        ),
    ],
)
def test_parent_words_in_comments_literals_or_column_names_stay_independent(phase, sql):
    scope.check_sql(sql, phase, {"app.cases", "app.messages"})


def test_phase_new_table_alterations_can_continue_in_later_migration(tmp_path):
    source = tmp_path / "migrations"
    source.mkdir()
    (source / "20261108100000_ag_create.sql").write_text(
        "create table app.roleplay_sessions(id int);"
    )
    (source / "20261108100001_ag_rls.sql").write_text(
        "alter table app.roleplay_sessions enable row level security;"
    )
    assert scope.check_migrations(source, {"app.messages"}) == 2


@pytest.mark.parametrize(
    "name", ["20260230010000_kb_bad.sql", "20261108100000_other_bad.sql", "x_kb_bad.sql"]
)
def test_scope_checker_rejects_malformed_migration_filenames(tmp_path, name):
    (tmp_path / name).write_text("create table knowledge.sources(id int);")
    with pytest.raises(ValueError):
        scope.check_migrations(tmp_path, set())


def test_scope_checker_rejects_duplicate_versions_across_phases(tmp_path):
    for phase in ["kb", "ag"]:
        (tmp_path / f"20261108100000_{phase}_test.sql").write_text("select 1;")
    with pytest.raises(ValueError, match="Duplicate"):
        scope.check_migrations(tmp_path, set())


@pytest.mark.parametrize(
    "branch,expected",
    [
        ("feat/knowledge-base", 1),
        ("feat/agent-companion", 1),
        ("feat/knowledge-ingestion-rag", 2),
        ("main", 0),
    ],
)
def test_cli_returns_failure_for_scope_violations_or_retired_profile(tmp_path, branch, expected):
    import json
    import subprocess
    import sys

    migrations = tmp_path / "supabase/migrations"
    migrations.mkdir(parents=True)
    manifest = tmp_path / "scripts/dev/schema-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"baseline_tables": {"app": ["messages"]}}))
    (migrations / "20261108100000_kb_outside.sql").write_text('create table "app".stolen(id int);')
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/dev/migration_scope_check.py"),
            "--root",
            str(tmp_path),
            "--branch",
            branch,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected
    if expected == 1:
        assert "20261108100000_kb_outside.sql" in result.stderr
        assert "outside the phase schemas" in result.stderr
