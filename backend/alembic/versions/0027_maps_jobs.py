"""Content-free Maps coordination, no query, area or persisted temporary results."""

from alembic import op

revision = "0027_maps_jobs"
down_revision = "0026_search_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE moodprint.ai_maps_searches (
        id uuid PRIMARY KEY,
        user_id uuid REFERENCES moodprint.users(id) ON DELETE SET NULL,
        parent_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        operation_id uuid NOT NULL REFERENCES moodprint.ai_search_usage(id),
        scope_id uuid, conversation_id uuid, session_id uuid,
        auth_version integer NOT NULL, data_version integer NOT NULL,
        status varchar(16) NOT NULL, version integer NOT NULL, provider_ref jsonb,
        cancel_requested boolean NOT NULL, cleanup_done boolean NOT NULL,
        deadline timestamptz NOT NULL, expires_at timestamptz NOT NULL,
        next_poll_at timestamptz NOT NULL, lease_until timestamptz, fence uuid,
        attempts integer NOT NULL, created_at timestamptz NOT NULL,
        CONSTRAINT uq_ai_maps_searches_operation_id UNIQUE (operation_id),
        CONSTRAINT ck_ai_maps_searches_status CHECK(status in ('starting','pending','ready','empty','failed','timed_out','cancelled','expired')),
        CONSTRAINT ck_ai_maps_searches_version CHECK(version >= 1 and attempts >= 0)
    )""")
    for column in ("user_id", "parent_run_id", "next_poll_at", "lease_until"):
        op.execute(f"CREATE INDEX ix_ai_maps_searches_{column} ON moodprint.ai_maps_searches({column})")
    op.execute("ALTER TABLE moodprint.ai_maps_searches ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON moodprint.ai_maps_searches FROM PUBLIC")
    op.execute("""DO $$ DECLARE r text; BEGIN
        FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
                EXECUTE 'REVOKE ALL ON moodprint.ai_maps_searches FROM ' || quote_ident(r);
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
            GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_maps_searches TO moodprint_runtime;
            CREATE POLICY backend_access ON moodprint.ai_maps_searches TO moodprint_runtime USING(true) WITH CHECK(true);
        END IF;
    END $$""")


def downgrade():
    raise RuntimeError("Forward-only jobs; drain/cleanup before any schema removal")
