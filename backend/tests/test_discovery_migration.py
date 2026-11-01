"""Rehearse the required destructive head against legacy data in an owned scratch DB."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.social_helpers import PROFILE

pytestmark = pytest.mark.postgres
BACKEND = Path(__file__).resolve().parents[1]
HEAD = "0024_three_agent_groups"  # 0020 is exercised through the chain that now ends here


def test_0020_preserves_journal_auth_matching_and_approved_memories():
    from tests.database_target import owned_scratch_database

    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Explicit owned disposable PostgreSQL required")
    with owned_scratch_database() as target:
        environment = {
            **os.environ,
            "DATABASE_URL": "",
            "DATABASE_MIGRATION_URL": target.render_as_string(hide_password=False),
        }

        def alembic(*args, check=True):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *args],
                cwd=BACKEND,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            if check:
                assert result.returncode == 0, result.stdout + result.stderr
            return result

        alembic("upgrade", "0019_journal")
        raw = target.set(drivername="postgresql").render_as_string(hide_password=False)
        uid, item, approved, pending, retired, memory, sid = (uuid4() for _ in range(7))
        profile = {**PROFILE, "activities": [], "availability": [], "strict_goal": False}
        draft_profile = {
            **profile,
            "discovery": {
                "version": 1,
                "intention": "experiences",
                "connection_approach": "activity-first",
                "featured_interests": ["music", "reading"],
            },
        }
        with psycopg.connect(raw) as db:
            # The original tables receive RLS in the separately reviewed initialization
            # bootstrap, not Alembic 0001. Reproduce that baseline before rehearsing 0020.
            db.execute("ALTER TABLE moodprint.matching_drafts ENABLE ROW LEVEL SECURITY")
            db.execute("ALTER TABLE moodprint.published_profiles ENABLE ROW LEVEL SECURITY")
            db.execute(
                "REVOKE ALL ON moodprint.matching_drafts, moodprint.published_profiles FROM PUBLIC"
            )
            db.execute(
                """insert into moodprint.users
              (id,auth_subject,alias,age_band,status,timezone,auth_version,data_version,profile_version)
              values (%s,%s,'Legacy','adult','active','Asia/Bangkok',1,3,1)""",
                (uid, uid),
            )
            db.execute(
                """insert into moodprint.private_items
              (id,user_id,text,origin,status,version) values (%s,%s,'Retired note','manual','active',1)""",
                (item, uid),
            )
            for identity, purpose, status, text in (
                (approved, "memory", "approved", "Approved memory"),
                (pending, "memory", "pending", "Unapproved source memory"),
                (retired, "private_item", "pending", "Retired proposal"),
            ):
                db.execute(
                    """insert into moodprint.memory_proposals
                  (id,user_id,bot_id,text,purpose,data_version,ai_consent_version,mem_consent_version,
                   version,status,source_id,source_version,created_at,expires_at)
                  values (%s,%s,'may',%s,%s,3,1,1,1,%s,%s,1,now(),now()+interval '1 day')""",
                    (identity, uid, text, purpose, status, item),
                )
            db.execute(
                """insert into moodprint.memories
              (id,user_id,bot_id,text,version,status,proposal_id,source_id,source_version)
              values (%s,%s,'may','Approved memory',1,'active',%s,%s,1)""",
                (memory, uid, approved, item),
            )
            db.execute(
                """insert into moodprint.journal_entries
              (id,user_id,local_date,timezone,mood,text) values (%s,%s,current_date,'Asia/Bangkok',4,'Private journal')""",
                (uuid4(), uid),
            )
            db.execute(
                """insert into moodprint.auth_sessions
              (id,user_id,token_hash,csrf_hash,provider_session_id,expires_at,revoked,auth_version)
              values (%s,%s,%s,%s,%s,%s,false,1)""",
                (sid, uid, "a" * 64, "b" * 64, uuid4(), datetime.now(UTC) + timedelta(days=1)),
            )
            db.execute(
                """insert into moodprint.matching_drafts(user_id,payload,version)
              values (%s,%s,7)""",
                (uid, Jsonb(draft_profile)),
            )
            db.execute(
                """insert into moodprint.published_profiles
              (id,user_id,payload,version,consent_version,valid,created_at,taxonomy_version)
              values (%s,%s,%s,1,2,true,now(),'v2')""",
                (uuid4(), uid, Jsonb(profile)),
            )
            before = db.execute("""select tablename,policyname,roles,qual,with_check
              from pg_policies where schemaname='moodprint' and tablename in
              ('matching_drafts','published_profiles','journal_entries','memories','memory_proposals')
              order by tablename,policyname""").fetchall()

        alembic("upgrade", "head")
        assert HEAD in alembic("current").stdout
        alembic(
            "upgrade", "head"
        )  # Idempotent migration runner, not rerunning raw destructive SQL.
        with psycopg.connect(raw) as db:
            assert db.execute("select to_regclass('moodprint.private_items')").fetchone() == (None,)
            assert db.execute(
                "select data_version,auth_version,profile_version from moodprint.users where id=%s",
                (uid,),
            ).fetchone() == (4, 1, 1)
            assert db.execute(
                "select text from moodprint.journal_entries where user_id=%s", (uid,)
            ).fetchone() == ("Private journal",)
            assert db.execute(
                "select payload,version from moodprint.matching_drafts where user_id=%s", (uid,)
            ).fetchone() == (draft_profile, 7)
            assert db.execute(
                "select payload,valid from moodprint.published_profiles where user_id=%s", (uid,)
            ).fetchone() == (profile, True)
            assert db.execute(
                "select revoked from moodprint.auth_sessions where id=%s", (sid,)
            ).fetchone() == (False,)
            assert db.execute(
                "select text,status from moodprint.memories where id=%s", (memory,)
            ).fetchone() == ("Approved memory", "active")
            assert db.execute(
                "select text,status,version from moodprint.memory_proposals where id=%s", (pending,)
            ).fetchone() == ("", "expired", 2)
            assert db.execute(
                "select text,status from moodprint.memory_proposals where id=%s", (approved,)
            ).fetchone() == ("Approved memory", "approved")
            assert db.execute(
                "select count(*) from moodprint.memory_proposals where id=%s", (retired,)
            ).fetchone() == (0,)
            after = db.execute("""select tablename,policyname,roles,qual,with_check
              from pg_policies where schemaname='moodprint' and tablename in
              ('matching_drafts','published_profiles','journal_entries','memories','memory_proposals')
              order by tablename,policyname""").fetchall()
            assert after == before
            db.execute("""DO $$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN
                CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
                CREATE ROLE service_role NOLOGIN; END IF;
            END $$""")
            for table in ("matching_drafts", "published_profiles"):
                assert db.execute(
                    "select relrowsecurity from pg_class where oid=%s::regclass",
                    (f"moodprint.{table}",),
                ).fetchone() == (True,)
                for role in ("anon", "authenticated", "service_role"):
                    assert not db.execute(
                        "select has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')",
                        (role, f"moodprint.{table}"),
                    ).fetchone()[0]
            db.rollback()  # Browser roles above are cluster-wide; leave no persistent roles.
        rollback = alembic("downgrade", "0019_journal", check=False)
        assert rollback.returncode != 0
        assert "Destructive rollback disabled" in rollback.stderr
        assert HEAD in alembic("current").stdout
