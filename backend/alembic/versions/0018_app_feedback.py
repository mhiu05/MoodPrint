"""Unlinked product feedback: constrained ratings, ephemeral receipts, content-free review audit.

Expand only. ``app_feedback`` deliberately has no user, session, address, conversation, device or
URL column and no foreign key, so a retained row can never be joined to a person. The only link is
the short-lived ``feedback_submission_receipts`` row (owner + idempotency key + payload digest),
which cascades *from* the feedback and *from* the user, never the other direction: purging a guest
or an expired receipt leaves the independently retained feedback in place. Value rules live in the
database (private immutable validators) so a direct SQL write is held to the same policy as the API.
Never roll this back with live data; switch collection off and keep retention running instead.
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_app_feedback"
down_revision = "0017_guest_security"
branch_labels = None
depends_on = None

FEEDBACK_TABLES = (
    "app_feedback",
    "feedback_submission_receipts",
    "feedback_review_events",
)
CATEGORIES = (
    "ease_of_use",
    "ai_quality",
    "interface",
    "performance",
    "bug",
    "missing_feature",
    "privacy_trust",
    "other",
)
CONTEXTS = ("general", "assistants", "mood", "memory", "privacy", "activities", "trial_end")
STATUSES = ("new", "reviewed", "planned", "resolved", "spam")
CATEGORIES_FUNCTION = "moodprint.feedback_categories_valid(text[])"
COMMENT_FUNCTION = "moodprint.feedback_comment_valid(text)"

# A CHECK cannot hold a subquery, so the array rules live in a private immutable function. Every
# branch is wrapped in coalesce(..., false): a NULL verdict would otherwise *pass* a CHECK.
CATEGORIES_SQL = (
    """CREATE OR REPLACE FUNCTION moodprint.feedback_categories_valid(items text[])
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = ''
AS $$
SELECT coalesce(
  items IS NOT NULL
  AND coalesce(cardinality(items), 0) <= 8
  AND array_position(items, NULL::text) IS NULL
  AND items <@ ARRAY["""
    + ",".join(f"'{code}'" for code in CATEGORIES)
    + """]::text[]
  AND coalesce(cardinality(items), 0) = (SELECT count(DISTINCT item) FROM unnest(items) AS item),
  false
)
$$"""
)

# At most 1000 code points, no C0 controls except tab/LF/CR, no DEL, no C1. NULL is a valid comment.
COMMENT_SQL = r"""CREATE OR REPLACE FUNCTION moodprint.feedback_comment_valid(value text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = ''
AS $$
SELECT value IS NULL OR (
  char_length(value) <= 1000
  AND value !~ '[\u0001-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]'
)
$$"""

ABUSE_SCOPES_BEFORE = (
    "intent",
    "intent_global",
    "creation_hour",
    "creation_day",
    "failed_signup",
    "feedback",
    "ai_minute",
    "voice_minute",
)
# One more window: attempts per identity per UTC minute (the network hour reuses ``feedback``).
ABUSE_SCOPES_AFTER = (*ABUSE_SCOPES_BEFORE, "feedback_attempt")


def in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({','.join(repr(value) for value in values)})"


def protection_statements(table: str) -> list[str]:
    """RLS on, no PUBLIC or Supabase API role access; only the backend runtime role."""
    return [
        f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY",
        f"REVOKE ALL ON moodprint.{table} FROM PUBLIC",
        f"""DO $acl$
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
END $acl$""",
    ]


def function_protection_statements(function: str) -> list[str]:
    """The CHECK functions run as the inserting role, so only the runtime role keeps EXECUTE."""
    return [
        f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC",
        f"""DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION {function} FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT EXECUTE ON FUNCTION {function} TO moodprint_runtime;
 END IF;
END $acl$""",
    ]


def function_statements() -> list[str]:
    """Both validators plus their grants; the fixture schema used by the tests runs the same SQL."""
    statements: list[str] = []
    for sql, function in ((CATEGORIES_SQL, CATEGORIES_FUNCTION), (COMMENT_SQL, COMMENT_FUNCTION)):
        statements.append(sql)
        statements.extend(function_protection_statements(function))
    return statements


def upgrade():
    for statement in function_statements():
        op.execute(statement)

    op.create_table(
        "app_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "categories",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("comment", sa.Text()),
        sa.Column("app_version", sa.String(64), nullable=False),
        sa.Column("context", sa.String(16), nullable=False, server_default="general"),
        sa.Column("account_kind", sa.String(10), nullable=False),
        sa.Column("disclosure_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_feedback")),
        sa.CheckConstraint("rating between 1 and 5", name=op.f("ck_app_feedback_rating")),
        sa.CheckConstraint(
            "moodprint.feedback_categories_valid(categories)",
            name=op.f("ck_app_feedback_categories"),
        ),
        sa.CheckConstraint(
            "moodprint.feedback_comment_valid(comment)", name=op.f("ck_app_feedback_comment")
        ),
        sa.CheckConstraint(in_list("context", CONTEXTS), name=op.f("ck_app_feedback_context")),
        sa.CheckConstraint(
            "account_kind in ('guest','registered')", name=op.f("ck_app_feedback_account_kind")
        ),
        sa.CheckConstraint(
            "disclosure_version ~ '^feedback-v[0-9]+$'",
            name=op.f("ck_app_feedback_disclosure_version"),
        ),
        sa.CheckConstraint(in_list("status", STATUSES), name=op.f("ck_app_feedback_status")),
        sa.CheckConstraint("version > 0", name=op.f("ck_app_feedback_version")),
        schema="moodprint",
    )
    op.create_index("ix_app_feedback_created_at", "app_feedback", ["created_at", "id"], schema="moodprint")
    op.create_index(
        "ix_app_feedback_status", "app_feedback", ["status", "created_at", "id"], schema="moodprint"
    )

    op.create_table(
        "feedback_submission_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("payload_digest", sa.CHAR(64), nullable=False),
        sa.Column("feedback_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_submission_receipts")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["moodprint.users.id"],
            name=op.f("fk_feedback_submission_receipts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["moodprint.app_feedback.id"],
            name=op.f("fk_feedback_submission_receipts_feedback_id_app_feedback"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name=op.f("uq_feedback_submission_receipts_user_id"),
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_feedback_submission_receipts_user_created",
        "feedback_submission_receipts",
        ["user_id", "created_at"],
        schema="moodprint",
    )
    op.create_index(
        "ix_feedback_submission_receipts_feedback_id",
        "feedback_submission_receipts",
        ["feedback_id"],
        schema="moodprint",
    )

    op.create_table(
        "feedback_review_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("feedback_id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("from_status", sa.String(12)),
        sa.Column("to_status", sa.String(12)),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_review_events")),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["moodprint.app_feedback.id"],
            name=op.f("fk_feedback_review_events_feedback_id_app_feedback"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["moodprint.users.id"],
            name=op.f("fk_feedback_review_events_staff_id_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action in ('status','redact')", name=op.f("ck_feedback_review_events_action")
        ),
        sa.CheckConstraint(
            "(from_status IS NULL OR " + in_list("from_status", STATUSES) + ")"
            " AND (to_status IS NULL OR " + in_list("to_status", STATUSES) + ")",
            name=op.f("ck_feedback_review_events_statuses"),
        ),
        sa.CheckConstraint(
            "action <> 'status' OR (from_status IS NOT NULL AND to_status IS NOT NULL)",
            name=op.f("ck_feedback_review_events_status_pair"),
        ),
        sa.CheckConstraint("resulting_version > 0", name=op.f("ck_feedback_review_events_version")),
        schema="moodprint",
    )
    op.create_index(
        "ix_feedback_review_events_feedback_created",
        "feedback_review_events",
        ["feedback_id", "created_at"],
        schema="moodprint",
    )
    op.create_index(
        "ix_feedback_review_events_staff_id",
        "feedback_review_events",
        ["staff_id"],
        schema="moodprint",
    )

    # The per-identity attempt window shares the existing HMAC bucket table.
    op.drop_constraint(
        op.f("ck_guest_abuse_buckets_scope"),
        "guest_abuse_buckets",
        schema="moodprint",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_guest_abuse_buckets_scope"),
        "guest_abuse_buckets",
        in_list("scope", ABUSE_SCOPES_AFTER),
        schema="moodprint",
    )

    for table in FEEDBACK_TABLES:
        for statement in protection_statements(table):
            op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Destructive rollback disabled; feedback rows are voluntary user data. Turn collection off "
        "and keep retention running instead of dropping the tables."
    )
