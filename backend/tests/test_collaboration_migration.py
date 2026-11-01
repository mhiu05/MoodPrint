"""M-P2-A (0023): child runs, per-edge sharing opt-in and content-free collaboration receipts (P2-01)."""

import importlib.util
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models import Base

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0023_collaboration.py"
TABLES = ("ai_sharing_permissions", "ai_collaborations")
BOTS = ("may", "guong", "nhip", "rure", "caunoi")
EDGES = {
    "nhip_energy_for_rure": ("rure", "nhip"),
    "nhip_habit_for_may": ("may", "nhip"),
    "rure_activity_for_guong": ("guong", "rure"),
}
# The schema exactly as 0022 left it; the ORM create_all already reflects 0023.
REWIND_TO_0022 = (
    "drop table moodprint.ai_collaborations",
    "drop table moodprint.ai_sharing_permissions",
    "alter table moodprint.ai_runs drop constraint ck_ai_runs_parent",
    "alter table moodprint.ai_runs drop constraint ck_ai_runs_origin",
    "drop index moodprint.ix_ai_runs_parent_run_id",
    "alter table moodprint.ai_runs drop column parent_run_id",
    "alter table moodprint.ai_runs add constraint ck_ai_runs_origin check (origin in ('user', 'proactive'))",
)
EXPECTED_CONSTRAINTS = {
    "ck_ai_runs_origin",
    "ck_ai_runs_parent",
    "fk_ai_runs_parent_run_id_ai_runs",
    "pk_ai_sharing_permissions",
    "ck_ai_sharing_permissions_edge",
    "ck_ai_sharing_permissions_version",
    "ck_ai_sharing_permissions_policy",
    "pk_ai_collaborations",
    "uq_ai_collaborations_primary_run_id",
    "ck_ai_collaborations_status",
    "ck_ai_collaborations_edge",
    "ck_ai_collaborations_rule",
    "ck_ai_collaborations_deny",
    "ck_ai_collaborations_deny_reason",
    "ck_ai_collaborations_failure",
    "ck_ai_collaborations_used",
    "ck_ai_collaborations_digest",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("collaboration_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


async def _rejects(connection, sql, params):
    savepoint = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await connection.execute(text(sql), params)
    await savepoint.rollback()


async def _accepts(connection, sql, params):
    savepoint = await connection.begin_nested()
    await connection.execute(text(sql), params)
    await savepoint.rollback()


async def _primary_run(connection, uid, *, bot="rure"):
    run = uuid4()
    await connection.execute(
        text(
            "insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, "
            "created_at, origin) values (:id, :u, :c, :b, 'completed', 2, now(), 'user')"
        ),
        {"id": run, "u": uid, "c": uuid4(), "b": bot},
    )
    return run


INSERT_COLLABORATION = (
    "insert into moodprint.ai_collaborations (id, user_id, primary_run_id, edge, rule_id, requester_bot, "
    "specialist_bot, status, deny_reason, failure_code, permission_version, data_version, input_schema, "
    "input_digest, used_in_reply) values (:id, :u, :run, :edge, :rule, :req, :spec, :status, :deny, :fail, "
    "1, 1, 'energy-hint-in-v1', :digest, :used)"
)


def _row(uid, run, **overrides):
    values = {
        "id": uuid4(), "u": uid, "run": run, "edge": "nhip_energy_for_rure", "rule": "R1",
        "req": "rure", "spec": "nhip", "status": "authorized", "deny": None, "fail": None,
        "digest": "a" * 64, "used": False,
    }
    values.update(overrides)
    return values


@pytest.mark.postgres
async def test_0023_upgrades_a_0022_schema_and_enforces_every_invariant(clients):
    app, actors = clients
    _, uid = actors[0]
    migration = _load_migration()
    assert migration.down_revision == "0022_proactive_messages"

    def migrate(connection):
        context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        with Operations.context(context):
            migration.upgrade()

    async with app.state.database.engine.begin() as connection:
        # A Phase 1 run exists before the upgrade and must survive unchanged.
        legacy = await _primary_run(connection, uid)
        for statement in REWIND_TO_0022:
            await connection.execute(text(statement))
        await connection.run_sync(migrate)

        names = set(
            (
                await connection.execute(
                    text(
                        "select conname from pg_constraint c join pg_class t on t.oid = c.conrelid "
                        "join pg_namespace n on n.oid = t.relnamespace "
                        "where n.nspname = 'moodprint' and t.relname = any(:tables)"
                    ),
                    {"tables": [*TABLES, "ai_runs"]},
                )
            ).scalars()
        )
        assert EXPECTED_CONSTRAINTS <= names, sorted(EXPECTED_CONSTRAINTS - names)
        assert not any(name.count("ck_") > 1 for name in names)
        assert await connection.scalar(
            text("select parent_run_id is null and origin = 'user' from moodprint.ai_runs where id = :r"),
            {"r": legacy},
        )
        for table in TABLES:
            assert await connection.scalar(
                text("select relrowsecurity from pg_class where oid = cast(:t as regclass)"),
                {"t": f"moodprint.{table}"},
            ), table
            assert await connection.scalar(
                text("select has_table_privilege('public', cast(:t as regclass), 'SELECT')"),
                {"t": f"moodprint.{table}"},
            ) is False, table
        index = await connection.scalar(
            text("select indexdef from pg_indexes where indexname = 'ix_ai_runs_parent_run_id'")
        )
        assert "WHERE" in index and "parent_run_id IS NOT NULL" in index

        # parent_run_id is present exactly for origin='collaboration' (and only those).
        child = (
            "insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, "
            "created_at, origin, parent_run_id) values (:id, :u, null, 'nhip', 'running', 1, now(), :o, :p)"
        )
        await _accepts(connection, child, {"id": uuid4(), "u": uid, "o": "collaboration", "p": legacy})
        await _rejects(connection, child, {"id": uuid4(), "u": uid, "o": "collaboration", "p": None})
        await _rejects(connection, child.replace("null, 'nhip'", ":c, 'nhip'"),
                       {"id": uuid4(), "u": uid, "o": "user", "p": legacy, "c": uuid4()})
        await _rejects(connection, child, {"id": uuid4(), "u": uid, "o": "delegated", "p": legacy})

        # Matrix: of 25 requester x specialist pairs per edge, only the declared one is accepted.
        for edge, (requester, specialist) in EDGES.items():
            for req in BOTS:
                for spec in BOTS:
                    params = _row(uid, legacy, edge=edge, req=req, spec=spec)
                    if (req, spec) == (requester, specialist):
                        await _accepts(connection, INSERT_COLLABORATION, params)
                    else:
                        await _rejects(connection, INSERT_COLLABORATION, params)
        await _rejects(connection, INSERT_COLLABORATION,
                       _row(uid, legacy, edge="caunoi_social_for_may", req="may", spec="caunoi"))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, rule="R9"))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, status="running"))
        # deny_reason iff denied; failure_code only for an unsuccessful outcome.
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, status="denied"))
        await _accepts(connection, INSERT_COLLABORATION, _row(uid, legacy, status="denied", deny="daily_cap"))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, deny="daily_cap"))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, fail="timeout"))
        await _accepts(connection, INSERT_COLLABORATION, _row(uid, legacy, status="timeout", fail="timeout"))
        # A distress match is never recorded, not even as a reason code.
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, status="denied", deny="distress"))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, status="denied", deny="edge_disabled"))
        # used_in_reply only on a completed collaboration; digests are sha256 hex.
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, used=True))
        await _accepts(connection, INSERT_COLLABORATION, _row(uid, legacy, status="completed", used=True))
        await _rejects(connection, INSERT_COLLABORATION, _row(uid, legacy, digest="not-a-digest"))
        # One consultation of a given specialist/edge per primary run.
        first = _row(uid, legacy)
        savepoint = await connection.begin_nested()
        await connection.execute(text(INSERT_COLLABORATION), first)
        with pytest.raises(IntegrityError):
            await connection.execute(text(INSERT_COLLABORATION), _row(uid, legacy))
        await savepoint.rollback()

        sharing = (
            "insert into moodprint.ai_sharing_permissions (user_id, edge, enabled, version, policy_version) "
            "values (:u, :e, true, :v, :p)"
        )
        await _accepts(connection, sharing, {"u": uid, "e": "nhip_habit_for_may", "v": 1, "p": "sharing-v1"})
        await _rejects(connection, sharing, {"u": uid, "e": "caunoi_mood_for_rure", "v": 1, "p": "sharing-v1"})
        await _rejects(connection, sharing, {"u": uid, "e": "nhip_habit_for_may", "v": 0, "p": "sharing-v1"})
        await _rejects(connection, sharing, {"u": uid, "e": "nhip_habit_for_may", "v": 1, "p": "sharing-v0"})

        # Offline review SQL is literal: '%' must never appear doubled.
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        assert "format(" not in source and "%%" not in source


async def _seed(app, uid, *, days_ago=0):
    from app.ai.collaboration.models import AiCollaboration, AiSharingPermission
    from app.infrastructure.database.models import AiRun, now

    async with app.state.database.sessions.begin() as db:
        primary = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="rure", status="completed")
        db.add(primary)
        await db.flush()
        child = AiRun(user_id=uid, conversation_id=None, bot_id="nhip", status="completed",
                      origin="collaboration", parent_run_id=primary.id)
        db.add(child)
        await db.flush()
        if await db.get(AiSharingPermission, (uid, "nhip_energy_for_rure")) is None:
            db.add(AiSharingPermission(user_id=uid, edge="nhip_energy_for_rure", enabled=True))
        row = AiCollaboration(
            user_id=uid, primary_run_id=primary.id, specialist_run_id=child.id,
            edge="nhip_energy_for_rure", rule_id="R1", requester_bot="rure", specialist_bot="nhip",
            status="completed", permission_version=1, data_version=1, input_schema="energy-hint-in-v1",
            input_digest="b" * 64, output_digest="c" * 64, used_in_reply=True,
            started_at=now() - timedelta(days=days_ago), finished_at=now() - timedelta(days=days_ago),
        )
        db.add(row)
        await db.flush()
        return row.id


async def _counts(app, uid):
    async with app.state.database.sessions() as db:
        return {
            table: await db.scalar(text(f"select count(*) from moodprint.{table} where user_id = :u"), {"u": uid})
            for table in TABLES
        }


@pytest.mark.postgres
@pytest.mark.parametrize("scope", ["account", "all_private"])
async def test_deletion_removes_collaboration_stores_of_only_that_user(clients, scope):
    from app.modules.users.lifecycle import process_deletions
    from app.modules.users.models import DataJob

    app, actors = clients
    (_, owner), (_, other) = actors
    await _seed(app, owner)
    await _seed(app, other)
    async with app.state.database.sessions.begin() as db:
        db.add(DataJob(user_id=owner, kind="deletion", scope=scope, status="queued"))
    await process_deletions(app)
    # The users row is a tombstone, so FK cascades never ran: rows must go explicitly.
    assert await _counts(app, owner) == dict.fromkeys(TABLES, 0)
    assert await _counts(app, other) == dict.fromkeys(TABLES, 1)


def test_guest_inventory_purges_collaboration_stores():
    from app.modules.guests.lifecycle import INVENTORY

    for table in TABLES:
        assert INVENTORY[table] == "purged"


@pytest.mark.postgres
async def test_retention_drops_receipts_older_than_90_days_only(clients):
    from app.ai.collaboration.models import AiCollaboration
    from app.jobs.retention import purge_expired

    app, actors = clients
    (_, first), (_, second) = actors
    old = await _seed(app, first, days_ago=91)
    recent = await _seed(app, second, days_ago=89)
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        remaining = set((await db.scalars(select(AiCollaboration.id))).all())
        assert remaining == {recent} and old not in remaining
        assert await db.scalar(select(func.count()).select_from(AiCollaboration)) == 1


@pytest.mark.postgres
async def test_deleting_a_primary_run_cascades_its_child_and_receipt(clients):
    from app.ai.collaboration.models import AiCollaboration
    from app.infrastructure.database.models import AiRun

    app, actors = clients
    _, uid = actors[0]
    receipt = await _seed(app, uid)
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiCollaboration, receipt)
        primary = row.primary_run_id
        await db.execute(text("delete from moodprint.ai_runs where id = :r"), {"r": primary})
    async with app.state.database.sessions() as db:
        assert await db.get(AiCollaboration, receipt) is None
        assert await db.scalar(select(func.count()).select_from(AiRun).where(AiRun.parent_run_id == primary)) == 0
