"""Content-free external liabilities survive deleting users, runs and transcripts."""

from alembic import op

revision = "0026_search_usage"
down_revision = "0025_search_citations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE moodprint.ai_search_usage (
        id uuid PRIMARY KEY,
        user_id uuid REFERENCES moodprint.users(id) ON DELETE SET NULL,
        parent_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        child_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        provider varchar(16) NOT NULL,
        ordinal integer NOT NULL,
        state varchar(16) NOT NULL,
        active boolean NOT NULL,
        reservation_nano_usd bigint NOT NULL,
        actual_nano_usd bigint,
        token_liability_nano_usd bigint NOT NULL,
        tokens_uncertain boolean NOT NULL,
        pricing_version varchar(100) NOT NULL,
        call_count integer NOT NULL,
        item_count integer NOT NULL,
        created_at timestamptz NOT NULL,
        updated_at timestamptz NOT NULL,
        CONSTRAINT uq_ai_search_usage_parent_run_id UNIQUE(parent_run_id, provider, ordinal),
        CONSTRAINT ck_ai_search_usage_provider CHECK(provider in ('openai_web','apify')),
        CONSTRAINT ck_ai_search_usage_state CHECK(state in ('reserved','dispatched','settled','uncertain')),
        CONSTRAINT ck_ai_search_usage_settlement CHECK((state = 'settled') = (actual_nano_usd is not null)),
        CONSTRAINT ck_ai_search_usage_money CHECK(reservation_nano_usd >= 0 and
            (actual_nano_usd is null or actual_nano_usd >= 0) and token_liability_nano_usd >= 0),
        CONSTRAINT ck_ai_search_usage_counts CHECK(ordinal = 1 and call_count between 0 and 1 and item_count between 0 and 5)
    )""")
    for column in ("user_id", "parent_run_id", "child_run_id"):
        op.execute(f"CREATE INDEX ix_ai_search_usage_{column} ON moodprint.ai_search_usage({column})")
    op.execute("CREATE INDEX ix_ai_search_usage_active ON moodprint.ai_search_usage(active, created_at)")
    op.execute("ALTER TABLE moodprint.ai_search_usage ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON moodprint.ai_search_usage FROM PUBLIC")
    op.execute("""DO $$ DECLARE r text; BEGIN
        FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
                EXECUTE 'REVOKE ALL ON moodprint.ai_search_usage FROM ' || quote_ident(r);
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
            GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_search_usage TO moodprint_runtime;
            CREATE POLICY backend_access ON moodprint.ai_search_usage TO moodprint_runtime USING(true) WITH CHECK(true);
        END IF;
    END $$""")


def downgrade():
    raise RuntimeError("Forward-only financial ledger; retain unsettled liabilities on rollback")
