"""Fixture DDL shared with Alembic so synthetic databases enforce the same guest guards.

ORM ``create_all`` cannot prove triggers or the provider bridge, so every disposable database that
builds its schema from metadata installs the reviewed 0016 guard functions/triggers and the 0017
guest-aware ``is_provider_session_active`` helper from the migrations themselves, plus a synthetic
reduced ``auth`` schema that models only what the helper reads.
"""

import importlib.util
from pathlib import Path

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic/versions"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"migration_{name}", _VERSIONS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load("0016_guest_foundation")
SECURITY_MIGRATION = _load("0017_guest_security")
GUARD_STATEMENTS = (
    MIGRATION.USER_GUARD_SQL,
    MIGRATION.USER_GUARD_TRIGGER_SQL,
    MIGRATION.SESSION_GUARD_SQL,
    MIGRATION.SESSION_GUARD_TRIGGER_SQL,
)
# Supabase's auth.sessions.user_id references auth.users; the reduced fixture keeps that parent
# row by trigger so existing direct session inserts stay permanent (is_anonymous=false) users.
AUTH_FIXTURE_STATEMENTS = (
    "create schema if not exists auth",
    "drop table if exists auth.sessions, auth.users cascade",
    "create table auth.users (id uuid primary key, is_anonymous boolean not null default false,"
    " raw_user_meta_data jsonb not null default '{}'::jsonb,"
    " created_at timestamptz not null default clock_timestamp())",
    "create table auth.sessions (id uuid primary key, user_id uuid not null)",
    """create or replace function auth.ensure_session_owner() returns trigger
language plpgsql as $$
begin
  insert into auth.users(id) values (new.user_id) on conflict (id) do nothing;
  return new;
end;
$$""",
    "create trigger sessions_owner before insert on auth.sessions"
    " for each row execute function auth.ensure_session_owner()",
)


async def install_guest_guards(connection) -> None:
    """Install the lifecycle immutability and session-cap guards on an async connection."""
    for statement in GUARD_STATEMENTS:
        await connection.exec_driver_sql(statement)


async def install_auth_fixture(connection) -> None:
    """Create the reduced synthetic ``auth`` schema and the current provider-session helper."""
    for statement in AUTH_FIXTURE_STATEMENTS:
        await connection.exec_driver_sql(statement)
    await connection.exec_driver_sql(SECURITY_MIGRATION.HELPER_SQL)
    await connection.exec_driver_sql(f"revoke all on function {SECURITY_MIGRATION.HELPER} from public")
