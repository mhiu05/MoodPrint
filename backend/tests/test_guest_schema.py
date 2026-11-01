"""Guest lifecycle schema: exact 7200s lifetime, immutability, private grants, safe 0015 upgrade."""

import importlib.util
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.postgres

BACKEND = Path(__file__).resolve().parents[1]
START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LIFETIME = timedelta(seconds=7200)


def load_migration(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND / "alembic/versions" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def add_user(database, **fields):
    from app.infrastructure.database.models import User

    uid = uuid4()
    async with AsyncSession(database, expire_on_commit=False) as db, db.begin():
        db.add(User(id=uid, auth_subject=uid, **fields))
    return uid


async def add_session(database, user_id, expires_at):
    async with database.begin() as conn:
        await conn.execute(
            text(
                "insert into moodprint.auth_sessions"
                "(id,user_id,token_hash,csrf_hash,provider_session_id,expires_at,revoked,auth_version)"
                " values (:id,:uid,:token,:csrf,:provider,:expires,false,1)"
            ),
            {
                "id": uuid4(),
                "uid": user_id,
                "token": uuid4().hex * 2,
                "csrf": uuid4().hex * 2,
                "provider": uuid4(),
                "expires": expires_at,
            },
        )


def guest_fields(delta: timedelta = LIFETIME):
    return {
        "account_kind": "guest",
        "guest_started_at": START,
        "guest_expires_at": START + delta,
    }


async def test_guest_lifetime_constraints_and_immutability(database):
    for seconds in (7199, 7201):
        with pytest.raises(IntegrityError):
            await add_user(database, **guest_fields(timedelta(seconds=seconds)))
    guest = await add_user(database, **guest_fields())

    # Registered rows carry no lifetime and guest rows must carry both ends.
    with pytest.raises(IntegrityError):
        await add_user(database, guest_started_at=START, guest_expires_at=START + LIFETIME)
    with pytest.raises(IntegrityError):
        await add_user(database, account_kind="guest")
    with pytest.raises(IntegrityError):
        await add_user(database, account_kind="visitor")

    legacy = await add_user(database)
    async with database.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "select account_kind, guest_started_at, guest_expires_at"
                    " from moodprint.users where id=:id"
                ),
                {"id": legacy},
            )
        ).one()
    assert tuple(row) == ("registered", None, None)

    # Even a statement that keeps the 7200s check satisfied cannot move, null or promote T.
    forbidden = {
        guest: [
            "account_kind='registered'",
            "guest_started_at=guest_started_at + interval '1 second',"
            " guest_expires_at=guest_expires_at + interval '1 second'",
            "guest_expires_at=guest_expires_at + interval '1 hour'",
            "account_kind='registered', guest_started_at=NULL, guest_expires_at=NULL",
        ],
        legacy: [
            "account_kind='guest', guest_started_at=now(),"
            " guest_expires_at=now() + interval '7200 seconds'",
        ],
    }
    for user_id, assignments in forbidden.items():
        for assignment in assignments:
            with pytest.raises(DBAPIError):
                async with database.begin() as conn:
                    await conn.execute(
                        text(f"update moodprint.users set {assignment} where id=:id"),
                        {"id": user_id},
                    )
    # Ordinary profile updates, including an early end, stay possible.
    async with database.begin() as conn:
        await conn.execute(
            text("update moodprint.users set alias='Khách', status='deleting' where id=:id"),
            {"id": guest},
        )
        row = (
            await conn.execute(
                text("select guest_started_at, guest_expires_at from moodprint.users where id=:id"),
                {"id": guest},
            )
        ).one()
    assert row[1] - row[0] == LIFETIME

    # A guest session can never outlive T; registered sessions are unaffected.
    await add_session(database, guest, START + LIFETIME)
    with pytest.raises(DBAPIError):
        await add_session(database, guest, START + LIFETIME + timedelta(seconds=1))
    with pytest.raises(DBAPIError):
        async with database.begin() as conn:
            await conn.execute(
                text(
                    "update moodprint.auth_sessions set expires_at=expires_at + interval '1 second'"
                    " where user_id=:id"
                ),
                {"id": guest},
            )
    await add_session(database, legacy, START + timedelta(days=30))
    async with database.connect() as conn:
        missing = await conn.scalar(
            text("select count(*) from moodprint.auth_sessions where created_at is null")
        )
    assert missing == 0


async def test_guest_tables_are_private(database):
    from app.modules.guests.models import GUEST_TABLES

    migration = load_migration("0016_guest_foundation")
    tables = [model.__tablename__ for model in GUEST_TABLES]
    assert len(tables) == 7
    async with database.connect() as conn:
        transaction = await conn.begin()
        try:
            for role in ("anon", "authenticated", "service_role", "moodprint_runtime"):
                await conn.exec_driver_sql(f"create role {role} nologin")
            for table in tables:
                for statement in migration.protection_statements(table):
                    await conn.exec_driver_sql(statement)
            for table in tables:
                qualified = f"moodprint.{table}"
                for role in ("anon", "authenticated", "service_role"):
                    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        allowed = await conn.scalar(
                            text("select has_table_privilege(:role, :table, :privilege)"),
                            {"role": role, "table": qualified, "privilege": privilege},
                        )
                        assert not allowed, f"{role} must not have {privilege} on {table}"
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    assert await conn.scalar(
                        text("select has_table_privilege('moodprint_runtime', :table, :p)"),
                        {"table": qualified, "p": privilege},
                    ), f"runtime needs {privilege} on {table}"
                assert await conn.scalar(
                    text("select relrowsecurity from pg_class where oid = cast(:table as regclass)"),
                    {"table": qualified},
                )
                policies = await conn.scalar(
                    text(
                        "select count(*) from pg_policies where schemaname='moodprint'"
                        " and tablename=:t and policyname='backend_access'"
                        " and roles = '{moodprint_runtime}'"
                    ),
                    {"t": table},
                )
                assert policies == 1
            for function in migration.GUARD_FUNCTIONS:
                for statement in migration.function_protection_statements(function):
                    await conn.exec_driver_sql(statement)
                for role in ("anon", "authenticated", "service_role"):
                    assert not await conn.scalar(
                        text("select has_function_privilege(:role, :function, 'EXECUTE')"),
                        {"role": role, "function": function},
                    )
        finally:
            await transaction.rollback()


def test_upgrade_from_0015_preserves_registered_rows_and_matches_models():
    from tests.database_target import require_local_test_database

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must identify a disposable real PostgreSQL database")
    require_local_test_database(url)
    def alembic(*args):
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    from tests.database_target import owned_scratch_database

    with owned_scratch_database(url) as scratch:
        env = {
            **os.environ,
            "DATABASE_URL": "",
            "DATABASE_MIGRATION_URL": scratch.render_as_string(hide_password=False),
        }
        alembic("upgrade", "0015_context_privacy")
        raw = scratch.set(drivername="postgresql").render_as_string(hide_password=False)
        uid, sid = uuid4(), uuid4()
        with psycopg.connect(raw, autocommit=True) as db:
            db.execute(
                "insert into moodprint.users(id,auth_subject,alias,age_band,status,timezone,"
                "auth_version,data_version,profile_version) values (%s,%s,'Cũ','adult','active',"
                "'Asia/Bangkok',1,1,0)",
                (uid, uid),
            )
            db.execute(
                "insert into moodprint.auth_sessions(id,user_id,token_hash,csrf_hash,"
                "provider_session_id,expires_at,revoked,auth_version) values "
                "(%s,%s,%s,%s,%s,now() + interval '1 day',false,1)",
                (sid, uid, "a" * 64, "b" * 64, uuid4()),
            )
        alembic("upgrade", "head")
        assert "0024_three_agent_groups (head)" in alembic("current").stdout
        with psycopg.connect(raw, autocommit=True) as db:
            kind = db.execute(
                "select account_kind, guest_started_at, guest_expires_at"
                " from moodprint.users where id=%s",
                (uid,),
            ).fetchone()
            assert kind == ("registered", None, None)
            created = db.execute(
                "select created_at from moodprint.auth_sessions where id=%s", (sid,)
            ).fetchone()
            assert created[0] is not None
            present = db.execute(
                "select count(*) from information_schema.tables where table_schema='moodprint'"
                " and table_name like 'guest\\_%%'"
            ).fetchone()[0]
            assert present == 7
            triggers = {
                row[0]
                for row in db.execute(
                    "select tgname from pg_trigger where not tgisinternal"
                    " and tgrelid in ('moodprint.users'::regclass,'moodprint.auth_sessions'::regclass)"
                )
            }
            assert {"users_lifecycle_immutable", "auth_sessions_lifetime_cap"} <= triggers
            public_execute = db.execute(
                "select count(*) from pg_proc p cross join lateral unnest(p.proacl) as acl"
                " where p.proname in ('guard_user_lifecycle','guard_session_lifetime')"
                " and acl::text like '=%%'"
            ).fetchone()[0]
            assert public_execute == 0
            unprotected = db.execute(
                "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace"
                " where n.nspname='moodprint' and c.relname like 'guest\\_%%' and c.relkind='r'"
                " and not c.relrowsecurity"
            ).fetchone()[0]
            assert unprotected == 0
            # Feedback storage (0018): present, RLS on, and no CRUD for PUBLIC or any API role.
            feedback_tables = {
                row[0]
                for row in db.execute(
                    "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace"
                    " where n.nspname='moodprint' and c.relkind='r' and c.relrowsecurity"
                    " and c.relname in ('app_feedback','feedback_submission_receipts',"
                    "'feedback_review_events')"
                )
            }
            assert feedback_tables == {
                "app_feedback",
                "feedback_submission_receipts",
                "feedback_review_events",
            }
            api_grants = db.execute(
                "select count(*) from information_schema.role_table_grants"
                " where table_schema='moodprint' and table_name in ('app_feedback',"
                "'feedback_submission_receipts','feedback_review_events')"
                " and grantee in ('PUBLIC','anon','authenticated','service_role')"
            ).fetchone()[0]
            assert api_grants == 0
            public_validators = db.execute(
                "select count(*) from pg_proc p cross join lateral unnest(p.proacl) as acl"
                " where p.proname in ('feedback_categories_valid','feedback_comment_valid')"
                " and acl::text like '=%%'"
            ).fetchone()[0]
            assert public_validators == 0
        drift = alembic("check")
        assert "No new upgrade operations detected" in drift.stdout
