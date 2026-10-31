"""V3: three default agents, smart orchestration receipts and AI group conversations.

Expand only. Every existing row satisfies the new CHECKs unchanged:

* the bot CHECKs accept the five legacy companions and the three V3 agents (no row is rewritten,
  no legacy conversation, message, memory or schedule is moved to another companion);
* ``ai_conversations.kind`` defaults to 'direct' (every existing conversation is direct);
  ``active_agent``/``active_agent_since`` are NULL; ``ai_messages.mentions`` defaults to '[]';
* ``ai_runs`` accepts origin 'agent' (child runs of V3 workflows; parent required as for
  Phase 2 'collaboration');
* two new private tables, RLS on, one ``backend_access`` policy for moodprint_runtime, nothing
  for client roles (as 0007/0019/0022/0023).

No default grants sharing: the four new edges exist only as allowed CHECK values; a user must
enable each one. An older image (head 0023) keeps working on this schema for its own data
(see docs/implementation-plans/three-agent-orchestration-group-chat/11). Forward-only.
"""

import sqlalchemy as sa

from alembic import op

revision = "0024_three_agent_groups"
down_revision = "0023_collaboration"
branch_labels = None
depends_on = None

SCHEMA = "moodprint"
LEGACY = ("may", "guong", "nhip", "rure", "caunoi")
V3 = ("dieuphoi", "nhatky", "hoatdong")
TABLES = ("ai_orchestration_steps", "ai_group_members")


def _in(values):
    return "(" + ",".join(f"'{value}'" for value in values) + ")"


ALL_BOTS = _in(LEGACY + V3)
MEMORY_BOTS = _in(("may", "guong", "nhip", "rure") + V3)
V3_IN = _in(V3)
EDGES = _in((
    "nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong",
    "dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong", "dieuphoi_handoff_nhatky",
    "dieuphoi_handoff_hoatdong",
))


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
    # Conversations: direct (one companion) or group (V3 agents as members).
    op.add_column("ai_conversations", sa.Column("kind", sa.String(8), nullable=False,
                                                server_default=sa.text("'direct'")), schema=SCHEMA)
    op.add_column("ai_conversations", sa.Column("active_agent", sa.String(16), nullable=True), schema=SCHEMA)
    op.add_column("ai_conversations", sa.Column("active_agent_since", sa.Integer(), nullable=True), schema=SCHEMA)
    replace_check("ai_conversations", "ck_ai_conversations_bot",
                  f"(kind = 'direct' and bot_id in {ALL_BOTS}) or (kind = 'group' and bot_id = 'group')")
    op.create_check_constraint(op.f("ck_ai_conversations_kind"), "ai_conversations",
                               "kind in ('direct','group')", schema=SCHEMA)
    op.create_check_constraint(
        op.f("ck_ai_conversations_active_agent_pair"), "ai_conversations",
        "(active_agent is null) = (active_agent_since is null) and (active_agent is null or kind = 'direct')",
        schema=SCHEMA,
    )
    op.create_check_constraint(op.f("ck_ai_conversations_active_agent"), "ai_conversations",
                               f"active_agent is null or active_agent in {V3_IN}", schema=SCHEMA)

    op.add_column("ai_messages", sa.Column("mentions", sa.dialects.postgresql.JSONB(), nullable=False,
                                           server_default=sa.text("'[]'::jsonb")), schema=SCHEMA)
    op.create_check_constraint(
        op.f("ck_ai_messages_mentions"), "ai_messages",
        "jsonb_typeof(mentions) = 'array' and jsonb_array_length(mentions) <= 4 "
        "and (actor = 'self' or jsonb_array_length(mentions) = 0)",
        schema=SCHEMA,
    )

    replace_check("ai_runs", "ck_ai_runs_origin", "origin in ('user', 'proactive', 'collaboration', 'agent')")
    replace_check("ai_runs", "ck_ai_runs_parent", "(origin in ('collaboration', 'agent')) = (parent_run_id is not null)")

    replace_check("ai_proactive_schedules", "ck_ai_proactive_schedules_bot", f"bot_id in {ALL_BOTS}")
    for table in ("memory_proposals", "memory_embedding_jobs", "memory_embeddings"):
        replace_check(table, f"ck_{table}_bot", f"bot_id in {MEMORY_BOTS}")
    replace_check("ai_sharing_permissions", "ck_ai_sharing_permissions_edge", f"edge in {EDGES}")

    op.create_table(
        "ai_orchestration_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("child_run_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("requester_bot", sa.String(16), nullable=False),
        sa.Column("target_bot", sa.String(16), nullable=True),
        sa.Column("edge", sa.String(48), nullable=True),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("deny_reason", sa.String(32), nullable=True),
        sa.Column("failure_code", sa.String(32), nullable=True),
        sa.Column("permission_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("detail", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_digest", sa.String(64), nullable=True),
        sa.Column("output_digest", sa.String(64), nullable=True),
        sa.Column("used_in_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind in ('plan','consult','handoff','group_select','group_reply')",
                           name=op.f("ck_ai_orchestration_steps_kind")),
        sa.CheckConstraint(
            "status in ('authorized','denied','completed','failed','timeout','cancelled','discarded')",
            name=op.f("ck_ai_orchestration_steps_status"),
        ),
        sa.CheckConstraint("requester_bot in ('dieuphoi','nhatky','hoatdong','group')",
                           name=op.f("ck_ai_orchestration_steps_requester")),
        sa.CheckConstraint(f"target_bot is null or target_bot in {V3_IN}", name=op.f("ck_ai_orchestration_steps_target")),
        sa.CheckConstraint("(kind in ('plan', 'group_select')) = (target_bot is null)",
                           name=op.f("ck_ai_orchestration_steps_target_kind")),
        sa.CheckConstraint("(status = 'denied') = (deny_reason is not null)", name=op.f("ck_ai_orchestration_steps_deny")),
        sa.CheckConstraint(
            "deny_reason is null or deny_reason in ('edge_disabled','journal_consent_off','daily_cap','budget',"
            "'time_budget','capacity','low_confidence','not_member','limit')",
            name=op.f("ck_ai_orchestration_steps_deny_reason"),
        ),
        sa.CheckConstraint("failure_code is null or status in ('failed', 'timeout', 'cancelled', 'discarded')",
                           name=op.f("ck_ai_orchestration_steps_failure")),
        sa.CheckConstraint("not used_in_reply or status = 'completed'", name=op.f("ck_ai_orchestration_steps_used")),
        sa.CheckConstraint("status = 'denied' or child_run_id is not null or finished_at is not null",
                           name=op.f("ck_ai_orchestration_steps_child")),
        sa.CheckConstraint("ordinal between 0 and 15", name=op.f("ck_ai_orchestration_steps_ordinal")),
        sa.CheckConstraint("jsonb_typeof(detail) = 'object'", name=op.f("ck_ai_orchestration_steps_detail")),
        sa.CheckConstraint(
            "(input_digest is null or input_digest ~ '^[0-9a-f]{64}$') "
            "and (output_digest is null or output_digest ~ '^[0-9a-f]{64}$')",
            name=op.f("ck_ai_orchestration_steps_digest"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_orchestration_steps_user_id_users")),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["moodprint.ai_runs.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_orchestration_steps_workflow_run_id_ai_runs")),
        sa.ForeignKeyConstraint(["child_run_id"], ["moodprint.ai_runs.id"], ondelete="SET NULL",
                                name=op.f("fk_ai_orchestration_steps_child_run_id_ai_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_orchestration_steps")),
        sa.UniqueConstraint("workflow_run_id", "kind", "ordinal", name="uq_ai_orchestration_steps_ordinal"),
        schema=SCHEMA,
    )
    op.create_index(op.f("ix_ai_orchestration_steps_user_started"), "ai_orchestration_steps",
                    ["user_id", "started_at"], schema=SCHEMA)
    op.create_index(op.f("ix_ai_orchestration_steps_workflow"), "ai_orchestration_steps",
                    ["workflow_run_id", "ordinal"], schema=SCHEMA)

    op.create_table(
        "ai_group_members",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default=sa.text("'active'")),
        sa.Column("journal_access", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("history_from_sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"bot_id in {V3_IN}", name=op.f("ck_ai_group_members_bot")),
        sa.CheckConstraint("status in ('active', 'removed')", name=op.f("ck_ai_group_members_status")),
        sa.CheckConstraint("(status = 'removed') = (removed_at is not null)", name=op.f("ck_ai_group_members_removed")),
        sa.CheckConstraint("journal_access = false or bot_id = 'nhatky'", name=op.f("ck_ai_group_members_journal")),
        sa.CheckConstraint("history_from_sequence >= 0 and version >= 1", name=op.f("ck_ai_group_members_bounds")),
        sa.ForeignKeyConstraint(["conversation_id"], ["moodprint.ai_conversations.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_group_members_conversation_id_ai_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_group_members_user_id_users")),
        sa.PrimaryKeyConstraint("conversation_id", "bot_id", name=op.f("pk_ai_group_members")),
        schema=SCHEMA,
    )
    op.create_index(op.f("ix_ai_group_members_user_id"), "ai_group_members", ["user_id"], schema=SCHEMA)

    for table in TABLES:
        protect(table)


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
