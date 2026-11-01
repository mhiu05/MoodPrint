"""M-P1-A (0021): expand-only bubble parts and server-originated runs over legacy data."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models import Base
from tests.fakes import make_test_model
from tests.test_chat_persistence import enable, key
from tests.test_context_privacy import turn

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0021_multi_message.py"

# The schema exactly as 0020 left it; the ORM create_all already reflects 0021.
REWIND_TO_0020 = (
    "alter table moodprint.ai_messages drop constraint uq_ai_messages_run_part",
    "alter table moodprint.ai_messages drop constraint ck_ai_messages_part",
    "alter table moodprint.ai_messages drop constraint ck_ai_messages_self_single",
    "alter table moodprint.ai_messages drop column part_index, drop column part_count",
    "alter table moodprint.ai_messages add constraint uq_ai_messages_run_id unique (run_id, actor)",
    "drop index moodprint.ix_ai_runs_user_origin_created",
    "alter table moodprint.ai_runs drop constraint ck_ai_runs_origin, drop constraint ck_ai_runs_slot, "
    "drop constraint ck_ai_runs_conversation",
    "alter table moodprint.ai_runs drop column origin, drop column proactive_slot",
    "alter table moodprint.ai_runs alter column conversation_id set not null",
    "alter table moodprint.ai_turns drop constraint ck_ai_turns_origin, drop constraint ck_ai_turns_session",
    "alter table moodprint.ai_turns drop column origin",
    "alter table moodprint.ai_turns alter column session_id set not null",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("multi_message_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


async def _rejects(connection, sql, params):
    savepoint = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await connection.execute(text(sql), params)
    await savepoint.rollback()


@pytest.mark.postgres
async def test_0021_preserves_legacy_rows_and_enforces_part_and_origin_invariants(clients):
    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert created.status_code == 201, created.text
    conversation_id = created.json()["conversationId"]
    url = f"/api/v1/ai/conversations/{conversation_id}"
    legacy = await turn(app, client, url, "Legacy synthetic input", make_test_model("Legacy reply"))
    migration = _load_migration()
    assert migration.down_revision == "0020_private_profile_retirement"

    def migrate(connection):
        # Same target metadata (and naming convention) as alembic/env.py, so the
        # constraint names asserted below are the names the reviewed SQL creates.
        context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        with Operations.context(context):
            migration.upgrade()

    # `clients` only uses a guarded disposable local *_test DB, never DATABASE_URL.
    async with app.state.database.engine.begin() as connection:
        acl = (
            "select relname, relrowsecurity, relacl::text from pg_class where oid in "
            "('moodprint.ai_messages'::regclass, 'moodprint.ai_runs'::regclass, 'moodprint.ai_turns'::regclass) "
            "order by relname"
        )
        before_acl = (await connection.execute(text(acl))).all()
        for statement in REWIND_TO_0020:
            await connection.execute(text(statement))
        await connection.run_sync(migrate)
        assert (await connection.execute(text(acl))).all() == before_acl
        names = set(
            (
                await connection.execute(
                    text(
                        "select conname from pg_constraint where conrelid in ('moodprint.ai_messages'::regclass, "
                        "'moodprint.ai_runs'::regclass, 'moodprint.ai_turns'::regclass) and contype in ('c','u')"
                    )
                )
            ).scalars()
        )
        assert {
            "ck_ai_messages_part", "ck_ai_messages_self_single", "uq_ai_messages_run_part",
            "ck_ai_runs_origin", "ck_ai_runs_slot", "ck_ai_runs_conversation",
            "ck_ai_turns_origin", "ck_ai_turns_session",
        } <= names
        assert "uq_ai_messages_run_id" not in names
        assert not any(name.count("ck_") > 1 for name in names)

        # Legacy rows receive the single-part/user defaults; nothing is backfilled or split.
        legacy_rows = (
            await connection.execute(
                text(
                    "select actor, part_index, part_count from moodprint.ai_messages "
                    "where run_id = :run order by sequence"
                ),
                {"run": legacy.id},
            )
        ).all()
        assert legacy_rows == [("self", 0, 1), ("bot", 0, 1)]
        origins = (
            await connection.execute(
                text(
                    "select r.origin, r.proactive_slot, t.origin from moodprint.ai_runs r "
                    "join moodprint.ai_turns t on t.run_id = r.id where r.id = :run"
                ),
                {"run": legacy.id},
            )
        ).one()
        assert tuple(origins) == ("user", None, "user")

        user_id, session_id = (
            await connection.execute(
                text("select user_id, session_id from moodprint.ai_turns where run_id = :run"),
                {"run": legacy.id},
            )
        ).one()
        run_id = uuid4()
        await connection.execute(
            text(
                "insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, created_at) "
                "values (:id, :user, :conversation, 'may', 'completed', 2, now())"
            ),
            {"id": run_id, "user": user_id, "conversation": conversation_id},
        )
        message = (
            "insert into moodprint.ai_messages (id, conversation_id, sequence, actor, text, cards, run_id, "
            "created_at, part_index, part_count) values (gen_random_uuid(), :conversation, :sequence, "
            ":actor, 'synthetic', '[]'::jsonb, :run, now(), :part, :count)"
        )
        base = {"conversation": conversation_id, "run": run_id}
        for part in (0, 1):
            await connection.execute(
                text(message), {**base, "sequence": 10 + part, "actor": "bot", "part": part, "count": 2}
            )
        # Duplicate part, part beyond count, and a multi-part user message are rejected.
        await _rejects(connection, message, {**base, "sequence": 12, "actor": "bot", "part": 1, "count": 2})
        await _rejects(connection, message, {**base, "sequence": 12, "actor": "bot", "part": 2, "count": 2})
        await _rejects(connection, message, {**base, "sequence": 12, "actor": "self", "part": 0, "count": 2})
        await _rejects(connection, message, {**base, "sequence": 12, "actor": "bot", "part": 4, "count": 5})

        run = (
            "insert into moodprint.ai_runs (id, user_id, conversation_id, bot_id, status, version, created_at, "
            "origin, proactive_slot) values (gen_random_uuid(), :user, :conversation, 'nhip', 'running', 1, "
            "now(), :origin, :slot)"
        )
        # A server-originated run may start before a target conversation exists.
        await connection.execute(
            text(run), {"user": user_id, "conversation": None, "origin": "proactive", "slot": "morning"}
        )
        await _rejects(connection, run, {"user": user_id, "conversation": None, "origin": "user", "slot": None})
        await _rejects(
            connection, run, {"user": user_id, "conversation": conversation_id, "origin": "user", "slot": "morning"}
        )
        await _rejects(
            connection, run, {"user": user_id, "conversation": None, "origin": "proactive", "slot": None}
        )
        await _rejects(
            connection, run, {"user": user_id, "conversation": None, "origin": "proactive", "slot": "noon"}
        )
        await _rejects(connection, run, {"user": user_id, "conversation": None, "origin": "system", "slot": None})

        turn_sql = (
            "insert into moodprint.ai_turns (run_id, user_id, scope_id, conversation_id, session_id, "
            "client_message_id, input_digest, data_version, context_policy, worker_id, lease_until, origin) "
            "values (:run, :user, gen_random_uuid(), null, :session, gen_random_uuid(), 'digest', 1, "
            "'proactive-text-v1', gen_random_uuid(), now(), :origin)"
        )
        proactive_run = await connection.scalar(
            text("select id from moodprint.ai_runs where origin = 'proactive' limit 1")
        )
        # A user turn always carries its session; a proactive turn never borrows one.
        await _rejects(connection, turn_sql, {"run": proactive_run, "user": user_id, "session": None, "origin": "user"})
        await _rejects(
            connection, turn_sql, {"run": proactive_run, "user": user_id, "session": session_id, "origin": "proactive"}
        )
        await connection.execute(
            text(turn_sql), {"run": proactive_run, "user": user_id, "session": None, "origin": "proactive"}
        )

    # The pre-migration application path (no part/origin columns written) keeps working.
    view = await client.get(url)
    assert view.status_code == 200, view.text
    assert [m["text"] for m in view.json()["messages"]][:2] == ["Legacy synthetic input", "Legacy reply"]
    await turn(app, client, url, "After migration", make_test_model("Still one bubble"))
