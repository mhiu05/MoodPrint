# 07 — Database and API Contracts

Source of truth for schema/API changes in the MVP productization. Pydantic models remain the API source; TypeScript types are regenerated (`uv run --locked python ../scripts/export_openapi.py` then `npm run contracts:generate`). All DTOs use the existing `DTO` base (camelCase aliases, `extra="forbid"`).

## 1. Migration sequence (expand-only)

| Revision | Phase/task | Adds | Depends on |
|---|---|---|---|
| `0011_social_stabilization` | B-04 | `connection_reads`, `users.last_seen_at`, 3 indexes | `0010_account_deletion` |
| `0012_matching_v2` | C-02 | `published_profiles.taxonomy_version`, `candidate_references.scoring_version` + `rank`, `matching_stats_daily` | `0011` |
| `0013_shared_activities` | D-01 | `connections.activity_seq`, `activity_sessions`, `activity_participants`, `activity_responses` | `0012` |
| `0014_moderation` | I-01 | `staff_roles`, `moderation_actions`, report workflow columns, `users.social_restricted_until`, `users.suspended_until` | `0013` |

Rules for every revision (from existing conventions):

1. File `backend/alembic/versions/00NN_<name>.py`, `revision = "00NN_<name>"`, `down_revision` = previous; `downgrade()` raises `RuntimeError("Expand-only migration; …")`.
2. New tables: `ENABLE ROW LEVEL SECURITY`; `REVOKE ALL … FROM PUBLIC`; `DO $acl$` block revoking `anon`, `authenticated`, `service_role` and granting CRUD + `CREATE POLICY backend_access … TO moodprint_runtime USING (true) WITH CHECK (true)` when the role exists. Use `'…' || quote_ident(r)`, **never** `format('%I')` (offline SQL keeps `%%`).
3. New columns on existing tables: `NOT NULL` only with a constant default (metadata-only in PG 17).
4. Update together: SQLAlchemy models (identical indexes/constraints), `backend/alembic/env.py` and `backend/tests/conftest.py` model imports (new modules), readiness literal in `backend/app/main.py` (`revision != "<new head>"`), `scripts/inspect_database.py` head check, `scripts/apply_supabase_review.py` `UpgradePlan` (+ review SQL and execution report paths under `docs/productization/migrations/`), `tests/test_database_operations.py` expectations if they enumerate tables.
5. Verify locally: `alembic upgrade head` + `alembic check` (no drift) on a fresh `*_test` DB; offline SQL generated and executed verbatim in a rehearsal DB.

## 2. Schema details

### 2.1 `0011_social_stabilization`

```sql
ALTER TABLE moodprint.users ADD COLUMN last_seen_at timestamptz;          -- null = unknown (treated as active until first write)
CREATE TABLE moodprint.connection_reads (
  connection_id uuid NOT NULL REFERENCES moodprint.connections(id),
  user_id uuid NOT NULL REFERENCES moodprint.users(id),
  last_read_seq bigint NOT NULL DEFAULT 0 CHECK (last_read_seq >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (connection_id, user_id)
);
CREATE INDEX ix_connection_reads_user_id ON moodprint.connection_reads(user_id);
CREATE INDEX ix_blocks_blocked_id ON moodprint.blocks(blocked_id);
CREATE INDEX ix_candidate_references_peer_id ON moodprint.candidate_references(peer_id);
CREATE INDEX ix_connection_requests_recipient_status ON moodprint.connection_requests(recipient_id, status);
```

Retrieval treats `last_seen_at IS NULL` as eligible for 30 days after deployment (backfill-free); `require_actor` writes it together with the existing sliding-expiry update (≤ once per 15 min per session).

### 2.2 `0012_matching_v2`

```sql
ALTER TABLE moodprint.published_profiles ADD COLUMN taxonomy_version varchar(8) NOT NULL DEFAULT 'v1';
ALTER TABLE moodprint.candidate_references ADD COLUMN scoring_version varchar(16) NOT NULL DEFAULT 'rules-v1';
ALTER TABLE moodprint.candidate_references ADD COLUMN rank smallint;
CREATE TABLE moodprint.matching_stats_daily (
  day date NOT NULL,
  scoring_version varchar(16) NOT NULL,
  impressions integer NOT NULL DEFAULT 0,
  requests integer NOT NULL DEFAULT 0,
  accepts integer NOT NULL DEFAULT 0,
  PRIMARY KEY (day, scoring_version)
);
```

Counters are incremented with `INSERT … ON CONFLICT (day, scoring_version) DO UPDATE SET x = x + 1` inside the transactions that mint references, create requests, and open rooms. No user identifiers.

### 2.3 `0013_shared_activities`

See [06 §7](06-shared-activities-design.md#7-database-schema-migration-0013_shared_activities) for full DDL.

### 2.4 `0014_moderation`

```sql
CREATE TABLE moodprint.staff_roles (
  user_id uuid PRIMARY KEY REFERENCES moodprint.users(id),
  role varchar(16) NOT NULL CHECK (role IN ('moderator','admin')),
  granted_at timestamptz NOT NULL DEFAULT now(),
  granted_by varchar(64) NOT NULL          -- operator label, not a user id
);
ALTER TABLE moodprint.reports ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE moodprint.reports ADD COLUMN connection_id uuid REFERENCES moodprint.connections(id);
ALTER TABLE moodprint.reports ADD COLUMN reviewed_at timestamptz;
ALTER TABLE moodprint.reports ADD COLUMN resolution varchar(16)
  CHECK (resolution IN ('dismissed','warned','restricted','suspended'));
CREATE INDEX ix_reports_status_created ON moodprint.reports(status, created_at);
CREATE TABLE moodprint.moderation_actions (
  id uuid PRIMARY KEY,
  report_id uuid REFERENCES moodprint.reports(id),
  subject_id uuid NOT NULL REFERENCES moodprint.users(id),
  staff_id uuid NOT NULL REFERENCES moodprint.users(id),
  action varchar(16) NOT NULL CHECK (action IN ('dismiss','warn','restrict','suspend','lift')),
  until_at timestamptz,
  note varchar(500) NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_moderation_actions_subject ON moodprint.moderation_actions(subject_id, created_at);
ALTER TABLE moodprint.users ADD COLUMN social_restricted_until timestamptz;
ALTER TABLE moodprint.users ADD COLUMN suspended_until timestamptz;
```

Report status values extend from `received` to `received | in_review | resolved` (app-level validation; existing column is `varchar(16)` without CHECK). Staff roles are granted only by an operator with the reviewed SQL path or `scripts/grant_staff_role.py` (local/test) — never through the API.

## 3. API changes

### 3.1 Social stabilization (B)

| Endpoint | Change |
|---|---|
| `GET /connection-requests` | `RequestView.peer?: PeerCardDTO` for `pending` rows while the pair is still eligible |
| `GET /connections` | `ConnectionView` adds `unreadCount: int`, `lastMessageAt: datetime?`, `lastMessagePreview: str?` (≤ 80 chars, sender label `self`/`peer`), `activeActivity: kind?` (after D) |
| `POST /connections/{id}/read` | **new** body `{seq: str}` → `{lastReadSeq: str}`; monotonic (never decreases); idempotent |
| `GET /social/summary` | **new** → `{pendingIncomingRequests: int, unreadConnections: int, activityInvites: int}`; returns zeros (not 403) when MATCH is off or user is not adult |
| alias everywhere | `pair_alias(a, b)` = `"Bạn đồng hành " + sha256(f"{low}:{high}")[:6]` used by candidate cards, requests, connections, export |

`PeerCardDTO`: `{alias, avatarSeed, profile: PublicProfile, reasons: list[str] (≤3), matchLabel: "many"|"some"}`.

### 3.2 Matching v2 (C)

| Endpoint | Change |
|---|---|
| `GET /taxonomy` | `TaxonomyDTO` v2: adds `activities`, `availability`, `categories: dict[str, list[str]]`, `version: "v2"` |
| `PUT /profiles/matching-draft` | `DraftInput` accepts `activities`, `availability`, `strictGoal` |
| `GET /matching/candidates` | `CandidateCardDTO` → `{candidateRef, alias, avatarSeed, profile, reasons, matchLabel, sharedActivities, scoringVersion, profileVersion, peerVersion}` |
| `GET /profiles/published/current` | `PublishedView.state` adds `"stale"` (published > 180 days or owner inactive > 30 days) |

### 3.3 Activities (D–G)

See [06 §8](06-shared-activities-design.md#8-api-endpoints-and-dtos). SSE event `activity_changed` added to `/connections/{id}/events`.

### 3.4 Moderation (I)

| Endpoint | Auth | Body → Response |
|---|---|---|
| `GET /admin/reports?status=&limit=` | staff | `AdminReportView[]` `{id, status, reason, createdAt, subjectRef, reporterRef, evidence[], priorActions: int}` (refs are opaque per-report ids; no emails) |
| `POST /admin/reports/{id}/claim` | staff | `{expectedVersion}` → `AdminReportView` (`in_review`) |
| `POST /admin/reports/{id}/resolve` | staff | `{expectedVersion, action: dismiss|warn|restrict|suspend, days?: 1..90, note}` → `AdminReportView` |
| `POST /admin/users/{subjectRef}/lift` | admin | `{note}` → `ActionReceipt` |
| `GET /session` | user | `SessionView.staff: "moderator"|"admin"|null`, `SessionView.notices: [{kind:"warning"|"restricted", until?}]` |
| `POST /reports` | user | `ReportInput` adds `selectedActivityResponses: [{sessionId, round}] (≤2)` |

Admin routes live in `backend/app/modules/moderation/admin_routes.py`, gated by `require_staff(role)` dependency that re-reads `staff_roles` per request. They stay in the exported OpenAPI schema so the typed client covers them (production does not serve `/openapi.json` anyway); the frontend renders the admin route only when `session.staff` is set, and the server enforces the role on every call.

### 3.5 AI quotas (I-05)

No new endpoint. `POST /ai/conversations/{id}/messages` may return `429 AI_DAILY_QUOTA` (per user) or `503 AI_BUDGET_EXHAUSTED` (global) with Vietnamese messages and `retryable: true`; `SessionView.features.aiQuotaRemaining: int | null`.

## 4. Error codes added

`ACTIVITY_IN_PROGRESS`, `ACTIVITY_CHANGED`, `ACTIVITY_INVITE_QUOTA`, `ACTIVITY_COOLDOWN`, `ROUND_CHANGED`, `RESPONSE_CONFLICT`, `NOT_FOCUS`, `NOT_COMPLETED`, `STAFF_REQUIRED`, `REPORT_CHANGED`, `ACCOUNT_SUSPENDED`, `SOCIAL_RESTRICTED`, `AI_DAILY_QUOTA`, `AI_BUDGET_EXHAUSTED`.

## 5. Settings added (`backend/app/core/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `MATCHING_SCORER` | `v1` | `v1` / `v2` / `shadow` |
| `ACTIVITIES_ENABLED` | `false` | Master switch; catalog returns `[]` and writes 503 when off |
| `ACTIVITY_KINDS` | `icebreaker,coop_quiz,focus` | Per-kind rollout/rollback |
| `MODERATION_ADMIN_ENABLED` | `false` | Admin routes return 404 when off |
| `AI_DAILY_TURNS_PER_USER` | `60` | Per-user daily AI turn quota (Asia/Bangkok day) |
| `AI_DAILY_BUDGET_USD` | `0` (disabled) | Global daily estimated spend ceiling; requires `AI_ACCOUNTING_ENABLED=true` |

All must be added to `backend/.env.example` and `deploy/runtime.env.example` with comments (no secrets).
