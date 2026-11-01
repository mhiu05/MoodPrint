"""V3-01 (0024): upgrade from a Phase 2 schema with real legacy data; every invariant enforced."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models import Base

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0024_three_agent_groups.py"
LEGACY = "('may','guong','nhip','rure','caunoi')"
MEMORY = "('may','guong','nhip','rure')"
# The schema exactly as 0023 left it; the ORM create_all already reflects 0024.
REWIND_TO_0023 = (
    "drop table moodprint.ai_group_members",
    "drop table moodprint.ai_orchestration_steps",
    "alter table moodprint.ai_conversations drop constraint ck_ai_conversations_active_agent",
    "alter table moodprint.ai_conversations drop constraint ck_ai_conversations_active_agent_pair",
    "alter table moodprint.ai_conversations drop constraint ck_ai_conversations_kind",
    "alter table moodprint.ai_conversations drop constraint ck_ai_conversations_bot",
    "alter table moodprint.ai_conversations drop column kind",
    "alter table moodprint.ai_conversations drop column active_agent",
    "alter table moodprint.ai_conversations drop column active_agent_since",
    f"alter table moodprint.ai_conversations add constraint ck_ai_conversations_bot check (bot_id in {LEGACY})",
    "alter table moodprint.ai_messages drop constraint ck_ai_messages_mentions",
    "alter table moodprint.ai_messages drop column mentions",
    "alter table moodprint.ai_runs drop constraint ck_ai_runs_parent",
    "alter table moodprint.ai_runs drop constraint ck_ai_runs_origin",
    "alter table moodprint.ai_runs add constraint ck_ai_runs_origin check (origin in ('user', 'proactive', 'collaboration'))",
    "alter table moodprint.ai_runs add constraint ck_ai_runs_parent check ((origin = 'collaboration') = (parent_run_id is not null))",
    "alter table moodprint.ai_proactive_schedules drop constraint ck_ai_proactive_schedules_bot",
    f"alter table moodprint.ai_proactive_schedules add constraint ck_ai_proactive_schedules_bot check (bot_id in {LEGACY})",
    *(
        statement
        for table in ("memory_proposals", "memory_embedding_jobs", "memory_embeddings")
        for statement in (
            f"alter table moodprint.{table} drop constraint ck_{table}_bot",
            f"alter table moodprint.{table} add constraint ck_{table}_bot check (bot_id in {MEMORY})",
        )
    ),
    "alter table moodprint.ai_sharing_permissions drop constraint ck_ai_sharing_permissions_edge",
    "alter table moodprint.ai_sharing_permissions add constraint ck_ai_sharing_permissions_edge check "
    "(edge in ('nhip_energy_for_rure', 'nhip_habit_for_may', 'rure_activity_for_guong'))",
)
EXPECTED = {
    "ck_ai_conversations_bot", "ck_ai_conversations_kind", "ck_ai_conversations_active_agent",
    "ck_ai_conversations_active_agent_pair", "ck_ai_messages_mentions", "ck_ai_runs_origin", "ck_ai_runs_parent",
    "pk_ai_orchestration_steps", "uq_ai_orchestration_steps_ordinal", "ck_ai_orchestration_steps_kind",
    "ck_ai_orchestration_steps_status", "ck_ai_orchestration_steps_target_kind", "ck_ai_orchestration_steps_deny",
    "ck_ai_orchestration_steps_deny_reason", "ck_ai_orchestration_steps_used", "ck_ai_orchestration_steps_child",
    "ck_ai_orchestration_steps_detail", "ck_ai_orchestration_steps_digest", "pk_ai_group_members",
    "ck_ai_group_members_bot", "ck_ai_group_members_status", "ck_ai_group_members_removed",
    "ck_ai_group_members_journal", "fk_ai_group_members_conversation_id_ai_conversations",
}


def _load():
    spec = importlib.util.spec_from_file_location("v3_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _rejects(connection, sql, params):
    savepoint = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await connection.execute(text(sql), params)
    await savepoint.rollback()


async def _accepts(connection, sql, params):
    savepoint = await connection.begin_nested()
    await connection.execute(text(sql), params)
    await savepoint.rollback()


async def _seed_phase2(connection, uid):
    """Legacy data of all five companions, as a Phase 2 account would have it."""
    ids = {}
    for bot in ("may", "guong", "nhip", "rure", "caunoi"):
        conversation, run = uuid4(), uuid4()
        await connection.execute(text(
            "insert into moodprint.ai_conversations (id, user_id, bot_id, title, version, created_at, updated_at, "
            "expires_at) values (:c, :u, :b, :t, 3, now(), now(), now() + interval '30 days')"),
            {"c": conversation, "u": uid, "b": bot, "t": f"Chuyện với {bot}"})
        await connection.execute(text(
            "insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, created_at, origin) "
            "values (:r, :u, :c, :b, 'completed', 2, now(), 'user')"), {"r": run, "u": uid, "c": conversation, "b": bot})
        for sequence, actor, body in ((2, "self", "Xin chào"), (3, "bot", f"Lời đáp của {bot}")):
            await connection.execute(text(
                "insert into moodprint.ai_messages (id, conversation_id, sequence, actor, text, cards, run_id, "
                "created_at) values (:id, :c, :s, :a, :t, '[]'::jsonb, :r, now())"),
                {"id": uuid4(), "c": conversation, "s": sequence, "a": actor, "t": body, "r": run})
        ids[bot] = (conversation, run)
    await connection.execute(text(
        "insert into moodprint.ai_proactive_schedules (id, user_id, bot_id, slot, enabled, local_time, weekdays, "
        "version, created_at, updated_at) values (:id, :u, 'nhip', 'morning', true, '07:30', 127, 3, now(), now())"),
        {"id": uuid4(), "u": uid})
    await connection.execute(text(
        "insert into moodprint.ai_sharing_permissions (user_id, edge, enabled, version) "
        "values (:u, 'nhip_habit_for_may', true, 2)"), {"u": uid})
    return ids


@pytest.mark.postgres
async def test_0024_upgrades_phase2_data_without_moving_or_merging_anything(clients):
    app, actors = clients
    _, uid = actors[0]
    migration = _load()
    assert migration.down_revision == "0023_collaboration"

    def migrate(connection):
        context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        with Operations.context(context):
            migration.upgrade()

    async with app.state.database.engine.begin() as connection:
        for statement in REWIND_TO_0023:
            await connection.execute(text(statement))
        legacy = await _seed_phase2(connection, uid)
        before = (await connection.execute(text(
            "select id, bot_id, title, version from moodprint.ai_conversations where user_id = :u order by id"),
            {"u": uid})).all()
        messages_before = await connection.scalar(text("select count(*) from moodprint.ai_messages"))
        await connection.run_sync(migrate)

        names = set((await connection.execute(text(
            "select conname from pg_constraint c join pg_class t on t.oid = c.conrelid "
            "join pg_namespace n on n.oid = t.relnamespace where n.nspname = 'moodprint' and t.relname = any(:t)"),
            {"t": ["ai_conversations", "ai_messages", "ai_runs", "ai_orchestration_steps", "ai_group_members",
                   "ai_proactive_schedules", "memory_proposals", "memory_embedding_jobs", "memory_embeddings",
                   "ai_sharing_permissions"]})).scalars())
        assert EXPECTED <= names, sorted(EXPECTED - names)
        assert not any(name.count("ck_") > 1 for name in names)

        # Nothing was rewritten: same companions, titles, versions, messages; all direct, no handoff.
        after = (await connection.execute(text(
            "select id, bot_id, title, version from moodprint.ai_conversations where user_id = :u order by id"),
            {"u": uid})).all()
        assert after == before
        assert await connection.scalar(text("select count(*) from moodprint.ai_messages")) == messages_before
        assert await connection.scalar(text(
            "select bool_and(kind = 'direct' and active_agent is null and active_agent_since is null) "
            "from moodprint.ai_conversations")) is True
        assert await connection.scalar(text(
            "select bool_and(mentions = '[]'::jsonb) from moodprint.ai_messages")) is True
        assert await connection.scalar(text(
            "select bot_id from moodprint.ai_proactive_schedules where user_id = :u"), {"u": uid}) == "nhip"
        # No default grants a V3 edge.
        assert await connection.scalar(text(
            "select count(*) from moodprint.ai_sharing_permissions where edge like 'dieuphoi_%'")) == 0

        conversation_sql = (
            "insert into moodprint.ai_conversations (id, user_id, bot_id, kind, title, version, created_at, updated_at, "
            "expires_at, active_agent, active_agent_since) values (:c, :u, :b, :k, 'x', 1, now(), now(), "
            "now() + interval '1 day', :a, :s)")
        base = {"u": uid, "a": None, "s": None}
        await _accepts(connection, conversation_sql, {**base, "c": uuid4(), "b": "dieuphoi", "k": "direct"})
        await _accepts(connection, conversation_sql, {**base, "c": uuid4(), "b": "group", "k": "group"})
        await _accepts(connection, conversation_sql, {"c": uuid4(), "u": uid, "b": "dieuphoi", "k": "direct",
                                                      "a": "nhatky", "s": 4})
        for bad in (
            {**base, "b": "group", "k": "direct"},
            {**base, "b": "dieuphoi", "k": "group"},
            {**base, "b": "robot", "k": "direct"},
            {**base, "b": "dieuphoi", "k": "direct", "a": "nhatky"},
            {**base, "b": "dieuphoi", "k": "direct", "a": "may", "s": 2},
            {**base, "b": "group", "k": "group", "a": "nhatky", "s": 2},
        ):
            await _rejects(connection, conversation_sql, {**bad, "c": uuid4()})

        # A child run needs a parent for both child origins; a user run never has one.
        run_sql = ("insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, created_at, "
                   "origin, parent_run_id) values (:id, :u, :c, :b, 'completed', 2, now(), :o, :p)")
        parent = legacy["may"][1]
        await _accepts(connection, run_sql, {"id": uuid4(), "u": uid, "c": None, "b": "nhatky", "o": "agent", "p": parent})
        await _rejects(connection, run_sql, {"id": uuid4(), "u": uid, "c": None, "b": "nhatky", "o": "agent", "p": None})
        await _rejects(connection, run_sql, {"id": uuid4(), "u": uid, "c": uuid4(), "b": "x", "o": "user", "p": parent})

        message_sql = ("insert into moodprint.ai_messages (id, conversation_id, sequence, actor, text, cards, run_id, "
                       "created_at, mentions) values (:id, :c, :s, :a, 'x', '[]'::jsonb, :r, now(), cast(:m as jsonb))")
        conversation = legacy["may"][0]
        run = uuid4()
        await connection.execute(text(run_sql), {"id": run, "u": uid, "c": uuid4(), "b": "may", "o": "user", "p": None})
        await _accepts(connection, message_sql, {"id": uuid4(), "c": conversation, "s": 9, "a": "self", "r": run,
                                                 "m": '["nhatky"]'})
        await _rejects(connection, message_sql, {"id": uuid4(), "c": conversation, "s": 9, "a": "bot", "r": run,
                                                 "m": '["nhatky"]'})
        await _rejects(connection, message_sql, {"id": uuid4(), "c": conversation, "s": 9, "a": "self", "r": run,
                                                 "m": '{"x": 1}'})

        step_sql = (
            "insert into moodprint.ai_orchestration_steps (id, user_id, workflow_run_id, child_run_id, kind, "
            "requester_bot, target_bot, edge, ordinal, status, deny_reason, data_version, detail, used_in_reply) "
            "values (:id, :u, :w, :child, :k, 'dieuphoi', :t, :e, :o, :st, :d, 1, cast(:detail as jsonb), :used)")
        ok = {"id": uuid4(), "u": uid, "w": parent, "child": parent, "k": "consult", "t": "nhatky",
              "e": "dieuphoi_consult_nhatky", "o": 0, "st": "completed", "d": None, "detail": "{}", "used": True}
        await _accepts(connection, step_sql, ok)
        await _accepts(connection, step_sql, {**ok, "k": "plan", "t": None, "e": None, "used": False})
        await _accepts(connection, step_sql, {**ok, "child": None, "st": "denied", "d": "edge_disabled", "used": False})
        for bad in (
            {"k": "plan"},                               # a plan has no target
            {"t": "may"},                                # never a legacy companion
            {"st": "failed"},                            # used only when completed
            {"st": "denied", "d": None, "used": False},  # a denial names its reason
            {"st": "denied", "d": "distress", "used": False},  # distress is never recorded
            {"child": None, "st": "authorized", "used": False},  # executed steps carry their run
            {"detail": "[]"},
            {"o": 16},
            {"k": "chat"},
        ):
            await _rejects(connection, step_sql, {**ok, "id": uuid4(), **bad})

        member_sql = ("insert into moodprint.ai_group_members (conversation_id, bot_id, user_id, status, journal_access, "
                      "removed_at) values (:c, :b, :u, :s, :j, :r)")
        group = uuid4()
        await connection.execute(text(conversation_sql), {**base, "c": group, "b": "group", "k": "group"})
        await _accepts(connection, member_sql, {"c": group, "b": "nhatky", "u": uid, "s": "active", "j": True, "r": None})
        for bad in (
            {"b": "may"}, {"b": "hoatdong", "j": True}, {"s": "removed"}, {"s": "gone"},
        ):
            await _rejects(connection, member_sql, {"c": group, "b": "nhatky", "u": uid, "s": "active", "j": False,
                                                    "r": None, **bad})

        # RLS: new tables private, no PUBLIC privileges.
        for table in migration.TABLES:
            assert await connection.scalar(text(
                "select relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                "where n.nspname = 'moodprint' and c.relname = :t"), {"t": table}) is True
            assert await connection.scalar(text(
                "select count(*) from information_schema.role_table_grants where table_schema = 'moodprint' "
                "and table_name = :t and grantee = 'PUBLIC'"), {"t": table}) == 0


@pytest.mark.postgres
async def test_account_deletion_and_group_cascade_remove_v3_rows(clients):
    """Group deletion cascades members/messages; the owner purge removes receipts and memberships."""
    from sqlalchemy import func, select

    from app.ai.models import AiConversation
    from app.ai.orchestration.models import AiGroupMember, AiOrchestrationStep
    from app.ai.proactive.lifecycle import purge_proactive
    from app.infrastructure.database.models import AiRun, now

    app, actors = clients
    _, uid = actors[0]
    _, other = actors[1]
    async with app.state.database.sessions.begin() as db:
        for owner in (uid, other):
            group = AiConversation(user_id=owner, bot_id="group", kind="group", expires_at=now())
            db.add(group)
            await db.flush()
            db.add(AiGroupMember(conversation_id=group.id, bot_id="nhatky", user_id=owner))
            run = AiRun(user_id=owner, conversation_id=group.id, bot_id="group", status="completed")
            db.add(run)
            await db.flush()
            db.add(AiOrchestrationStep(user_id=owner, workflow_run_id=run.id, kind="group_select",
                                       requester_bot="group", ordinal=0, status="completed", data_version=1,
                                       finished_at=now()))
    async with app.state.database.sessions.begin() as db:
        await purge_proactive(db, uid)
        await db.execute(AiConversation.__table__.delete().where(AiConversation.user_id == uid))
    async with app.state.database.sessions() as db:
        for model in (AiGroupMember, AiOrchestrationStep):
            assert await db.scalar(select(func.count()).select_from(model).where(model.user_id == uid)) == 0
            # Another account is untouched.
            assert await db.scalar(select(func.count()).select_from(model).where(model.user_id == other)) == 1
