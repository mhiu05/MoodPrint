"""School profiles and the direct-conversation bot id troly.

Expand only. Existing rows satisfy the widened conversation check. Proactive,
memory and group checks stay on the frozen bot set. Forward-only on hosted
databases; downgrade refuses once a school profile or troly conversation exists.
"""

import sqlalchemy as sa

from alembic import op

revision = "0030_school_profiles"
down_revision = "0029_journal_intelligence"
branch_labels = None
depends_on = None

SCHEMA = "moodprint"


def protect(table):
    op.execute(f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON moodprint.{table} FROM PUBLIC")
    op.execute(f"""DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.{table} FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.{table} TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.{table} FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$""")


def replace_check(table, name, condition):
    op.drop_constraint(op.f(name), table, type_="check", schema=SCHEMA)
    op.create_check_constraint(op.f(name), table, condition, schema=SCHEMA)


def upgrade():
    from app.ai.models import CONVERSATION_BOT_CHECK

    op.create_table(
        "school_profiles",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("age_group", sa.String(8), nullable=False),
        sa.Column("terms_version", sa.String(32), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("neutral_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("age_group in ('11-14', '15-17')", name="age_group"),
        sa.CheckConstraint("(terms_version is null) = (terms_accepted_at is null)", name="terms_pair"),
        sa.CheckConstraint("version >= 1", name="version"),
        schema=SCHEMA,
    )
    protect("school_profiles")
    replace_check("ai_conversations", "ck_ai_conversations_bot", CONVERSATION_BOT_CHECK)


def downgrade():
    from app.ai.agents import FROZEN_IDS, sql_in

    op.execute("""DO $guard$ BEGIN
 IF EXISTS (SELECT 1 FROM moodprint.school_profiles)
 OR EXISTS (SELECT 1 FROM moodprint.ai_conversations WHERE bot_id = 'troly') THEN
  RAISE EXCEPTION 'school safety data exists; use compatible image rollback';
 END IF;
END $guard$""")
    op.drop_table("school_profiles", schema=SCHEMA)
    previous = (
        f"(kind = 'direct' and bot_id in {sql_in(FROZEN_IDS)}) or (kind = 'group' and bot_id = 'group')"
    )
    replace_check("ai_conversations", "ck_ai_conversations_bot", previous)
