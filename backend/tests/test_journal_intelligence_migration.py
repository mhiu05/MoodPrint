"""0029 preserves approved data, enforces provenance, and cascades derivatives."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0029_journal_intelligence.py"


@pytest.fixture
async def migrated(clients):
    app, actors = clients
    spec = importlib.util.spec_from_file_location("journal_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    uid = actors[0][1]
    entry, memory, proposal = uuid4(), uuid4(), uuid4()

    def execute(connection, direction):
        with Operations.context(MigrationContext.configure(connection)):
            getattr(migration, direction)()

    async with app.state.database.engine.begin() as db:
        await db.run_sync(execute, "downgrade")
        await db.execute(text(
            "insert into moodprint.memories (id,user_id,bot_id,text,version,status,proposal_id) "
            "values (:m,:u,'nhatky','Bạn thích vẽ tranh.',1,'active',:p)"
        ), {"m": memory, "u": uid, "p": proposal})
        await db.execute(text(
            "insert into moodprint.journal_entries (id,user_id,local_date,timezone,mood) "
            "values (:e,:u,current_date,'Asia/Bangkok',3)"
        ), {"e": entry, "u": uid})
        await db.run_sync(execute, "upgrade")
    yield app, uid, entry, memory, proposal, migration


async def test_upgrade_preserves_every_approved_memory(migrated):
    app, _uid, _entry, memory, proposal, _migration = migrated
    async with app.state.database.sessions() as db:
        row = (await db.execute(text("select origin,proposal_id,source_entry_id from moodprint.memories where id=:m"), {"m": memory})).one()
        assert row == ("approved", proposal, None)


@pytest.mark.parametrize(("origin", "proposal", "source", "version"), [
    ("approved", False, False, None), ("journal_auto", False, False, 1),
    ("journal_auto", True, True, 1), ("journal_auto", False, True, 0),
    ("journal_auto", False, True, None),
])
async def test_origin_check_rejects_mixed_rows(migrated, origin, proposal, source, version):
    app, uid, entry, _memory, _proposal, _migration = migrated
    async with app.state.database.sessions.begin() as db:
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                await db.execute(text(
                    "insert into moodprint.memories (id,user_id,bot_id,text,version,status,proposal_id,origin,source_entry_id,source_entry_version) "
                    "values (:id,:u,'nhatky','Bạn thích đọc sách.',1,'active',:p,:o,:e,:v)"
                ), {"id": uuid4(), "u": uid, "p": uuid4() if proposal else None,
                    "o": origin, "e": entry if source else None, "v": version})


async def seed_derivatives(db, uid, entry):
    await db.execute(text(
        "insert into moodprint.journal_entry_embeddings (id,entry_id,user_id,entry_version,settings_version,content_sha256,model,dimensions,embedding) "
        "values (:id,:e,:u,1,1,:sha,'synthetic',256,cast(:vector as extensions.vector))"
    ), {"id": uuid4(), "e": entry, "u": uid, "sha": "0" * 64, "vector": "[" + ",".join(["1"] + ["0"] * 255) + "]"})
    await db.execute(text(
        "insert into moodprint.journal_ai_jobs (id,entry_id,user_id,kind,entry_version,settings_version,model,dimensions,available_at) "
        "values (:id,:e,:u,'embed',1,1,'synthetic',256,clock_timestamp())"
    ), {"id": uuid4(), "e": entry, "u": uid})
    await db.execute(text(
        "insert into moodprint.memories (id,user_id,bot_id,text,version,status,origin,source_entry_id,source_entry_version) "
        "values (:id,:u,'nhatky','Bạn thích đọc sách.',1,'active','journal_auto',:e,1)"
    ), {"id": uuid4(), "u": uid, "e": entry})


async def test_entry_delete_cascades_vectors_jobs_and_auto_memories(migrated):
    app, uid, entry, memory, _proposal, _migration = migrated
    async with app.state.database.sessions.begin() as db:
        await seed_derivatives(db, uid, entry)
        await db.execute(text("delete from moodprint.journal_entries where id=:e"), {"e": entry})
        for table in ("journal_entry_embeddings", "journal_ai_jobs"):
            assert await db.scalar(text(f"select count(*) from moodprint.{table}")) == 0
        assert (await db.execute(text("select id,origin from moodprint.memories"))).all() == [(memory, "approved")]


async def test_ai_runs_accepts_journal_origin_without_conversation(migrated):
    app, uid, *_rest = migrated
    async with app.state.database.sessions.begin() as db:
        await db.execute(text(
            "insert into moodprint.ai_runs (id,user_id,bot_id,status,version,created_at,origin) "
            "values (:id,:u,'nhatky','completed',1,now(),'journal')"
        ), {"id": uuid4(), "u": uid})


async def test_new_tables_have_rls_and_no_public_grants(migrated):
    app, *_rest = migrated
    async with app.state.database.sessions() as db:
        for table in ("journal_ai_settings", "journal_entry_embeddings", "journal_ai_jobs"):
            assert await db.scalar(text(
                "select relrowsecurity from pg_class where oid=cast(:table as regclass)"
            ), {"table": "moodprint." + table}) is True
            assert await db.scalar(text(
                "select count(*) from information_schema.role_table_grants "
                "where table_schema='moodprint' and table_name=:t and grantee='PUBLIC'"
            ), {"t": table}) == 0


async def test_downgrade_refuses_when_auto_memories_exist(migrated):
    app, uid, entry, _memory, _proposal, migration = migrated
    async with app.state.database.engine.begin() as db:
        await seed_derivatives(db, uid, entry)
        def downgrade(connection):
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
        with pytest.raises(Exception, match="journal"):
            async with db.begin_nested():
                await db.run_sync(downgrade)
