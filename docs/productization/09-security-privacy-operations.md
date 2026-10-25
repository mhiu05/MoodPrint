# 09 — Security, Privacy and Operations

Baseline is strong (opaque cookies, CSRF, provider-session check, consent versions, RLS deny-by-default for Supabase API roles, content-free logs). This plan closes the gaps that matter for real users and keeps every control inside the existing monolith.

## 1. Threat model summary (new surfaces)

| Surface | Threat | Control |
|---|---|---|
| Activity endpoints | Non-member reads/acts; stale tab after block; replayed writes; peer answer leakage | `svc.live_room` on every call; abort hooks; idempotency receipts + `expectedVersion`; viewer-projected DTOs (reciprocal reveal, hidden `correctIndex`, no peer feedback) |
| Activity invites | Harassment by repeated invites | Per-connection/per-user quotas, decline cooldown, block aborts |
| Request sender card | Profile scraping | Card only for the counterpart of a pending request while still eligible; same data already visible as a candidate |
| Read markers / unread | Activity surveillance | Never exposed to peers (no read receipts) |
| Admin routes | Privilege escalation; insider over-reach | `staff_roles` checked per request; grants only via operator SQL; admin sees only reporter-selected evidence, never full transcripts; every action logged in `moderation_actions` |
| Matching | Inference of private data | Inputs restricted to published profile; import allowlist test; reasons only from shared published items |
| AI | Cost abuse | Daily per-user quota + global ceiling (fail closed) |

## 2. Authentication and authorization

- Keep: opaque session cookie (HttpOnly, Secure in production, SameSite=Strict), CSRF header digest, Origin check, sliding idle expiry, absolute cookie max-age, live `auth.sessions` check, re-auth for export/account deletion.
- Add (I-03): `users.suspended_until`; `verify_session` rejects with `403 ACCOUNT_SUSPENDED` while suspended; suspension bumps `auth_version` (kills sessions) and aborts activities. `social_restricted_until` makes `assert_purpose("MATCH")` fail with `403 SOCIAL_RESTRICTED` and removes the user from retrieval; existing rooms are closed through `invalidate_user_social`.
- Every new route uses `require_actor`; pair-scoped writes use `svc.pair_transaction` and the canonical lock order.

## 3. CSRF and session protections

No change in mechanism. New write endpoints (activities, reads, admin) automatically inherit CSRF/Origin checks from `require_actor`. SSE remains GET-only. Admin routes additionally require a re-auth timestamp < 12 h (`AuthSession.reauthenticated_at`) to reduce stolen-session impact.

## 4. Strict user isolation

- Tests: for every new endpoint, a third synthetic user (C) receives 404/403 for reads and writes (pattern in `tests/test_social.py`).
- DTO projection helpers are the only path from rows to responses (`activities/schemas.py: project(session, viewer)`), with unit tests asserting hidden fields are absent.

## 5. Consent boundaries

| Consent | Effect on new features |
|---|---|
| MATCH off | Rooms close (existing), activities abort, summary endpoint returns zeros, discovery/requests 403 |
| AI off | Unchanged (AI only) |
| Profile republish/withdraw | Discovery visibility only; rooms and activities continue (DR-03) |

Settings copy (`consentWithdrawal.MATCH` in `RealApp.tsx`) must add: "…và dừng mọi hoạt động chung đang diễn ra."

## 6. Age restrictions

Social features remain 18+ (self-declared year + explicit 18 attestation in the boundary year). Risk accepted for beta with mitigations: report reason "Có thể chưa đủ 18 tuổi" → moderator can suspend; invite-only beta onboarding.

## 7. Blocking, reporting, moderation workflow

- Blocking (existing) additionally aborts activities (D-05).
- Reporting accepts up to 2 messages + 2 activity responses as evidence (I-04). Evidence is copied at report time (as today) so later retention does not erase it; reports are retained 1 year (decision; documented in privacy notice).
- Workflow: `received` → `in_review` (claim) → `resolved` with resolution `dismissed | warned | restricted | suspended`. Target SLA: triage ≤ 48 h during beta. Reporter sees status via existing `GET /reports/{id}` (status text only).
- Warning: shown to the subject as a session notice ("Tài khoản của bạn đã nhận một cảnh báo về quy tắc cộng đồng") until acknowledged (client-only dismissal acceptable in MVP).
- Emergency content (self-harm, threats): moderator playbook in `docs/productization/runbooks/moderation.md` (created in I-02) with escalation contacts — **requires product owner input (Q-03)**.

## 8. Data export and deletion

- Export `social` section adds activities (own sessions/answers/feedback) and read markers (D-05/I-04).
- Account deletion removes own activity responses/feedback/read markers; aborts sessions; anonymizes messages as today.
- Moderation records about a deleted user keep `subject_id` (tombstoned user row) for 1 year for safety (documented).

## 9. Provider privacy

| Provider | Data | Current control | Gap |
|---|---|---|---|
| OpenAI | AI turns (consented), Nhịp mood stats (per-turn), voice audio (flag) | `store:false`, tracing off, retries 0 (prior evidence) | Account-level retention/region not verified (Q-02) |
| Voyage AI | Approved memories (flag) | Capability flag; per-user opt-in | Retention/region not verified; keep off for beta unless approved |
| Supabase | All app data (ap-northeast-1 pooler) | RLS, runtime role, no Data API exposure | Plan backups/PITR unverified |
| AWS | Logs (content-free) | CloudWatch | Retention period to set (30 days) |

I-08 drafts `docs/productization/privacy-notice-draft.md` (Vietnamese) covering purposes, providers, retention table, rights (export/delete), contact. Legal sign-off is an external gate.

## 10. Data retention (target)

| Data | Retention |
|---|---|
| Human messages | 90 days (existing) |
| Activity responses / terminal sessions | 90 days |
| Connection reads | until connection closed + 90 days, or deletion |
| Candidate references | 15 min validity, purged after 24 h (existing) |
| `matching_stats_daily` | 1 year (no identifiers) |
| Reports + moderation actions | 1 year |
| AI conversations | user setting ≤ 90 days (existing) |
| Outbox | purge all rows (A-05) |

## 11. PostgreSQL RLS and least privilege

Unchanged model: schema `moodprint` not exposed via Data API; RLS on every table; only `moodprint_runtime` has a permissive policy; runtime login has no BYPASSRLS/CREATE/raw Auth. Each new migration repeats the ACL block (checked by `scripts/verify_migration_review.py` during review). Run Supabase advisors (read-only) after each hosted apply.

## 12. Logging and monitoring

- Keep content-free logs (no message text, answers, tags, emails, IDs in error logs).
- Add structured counters as log lines (`metric=<name> value=<n>`): `activity_started`, `activity_completed`, `activity_aborted reason=`, `ai_quota_denied`, `ai_budget_denied`, `report_created`, `moderation_action action=`, `sse_streams_open` (sampled every 60 s).
- CloudWatch (I-07, config only until AWS exists): metric filters on the above plus 5xx rate; alarms: 5xx > 2 % over 5 min, readiness failing 2 checks, `ai_run_failed` rate > 20 % over 15 min, budget ≥ 80 % (log line emitted by the quota guard), disk > 80 %.

## 13. AI quotas and cost limits

- `AI_DAILY_TURNS_PER_USER` (default 60): count `ai_runs` for the user since local midnight (Asia/Bangkok) inside `admission()` (already under an advisory lock).
- `AI_DAILY_BUDGET_USD` (default 0 = off): sum `ai_usage.estimated_nano_usd` since UTC midnight; deny new runs when ≥ ceiling; log at 80 %. Requires `AI_ACCOUNTING_ENABLED=true` (hosted schema already has `ai_usage`).
- Fail closed with honest copy; never truncate an in-flight run.

## 14. Backup and restore

- Weekly logical backup of schema `moodprint` (`pg_dump --schema=moodprint -Fc`) by the operator, stored encrypted off-host; before every hosted migration a fresh dump (existing practice).
- Quarterly restore drill into a disposable `*_test` DB; verify row counts and `alembic current`. Runbook: `docs/productization/runbooks/backup-restore.md` (I-07).
- Confirm Supabase plan entitlements (daily backups/PITR) — unverified (Q-04).

## 15. Deployment and rollback

- Release = immutable image built from a reviewed `main` SHA (existing gated workflow). Migrations applied **before** the app that needs them, always expand-only, via reviewed offline SQL.
- Rollback = redeploy previous image digest; schema stays; feature flags (`ACTIVITIES_ENABLED`, `ACTIVITY_KINDS`, `MATCHING_SCORER`, `MODERATION_ADMIN_ENABLED`) disable new behavior without code rollback. Details in [11](11-migration-and-rollback.md).

## 16. Performance for ~50 users

Targets (PR-O-03): writes p95 < 800 ms, reads p95 < 500 ms, SSE first event p95 < 2 s at 50 concurrent users with 1 s think time on the staging host; 0 integrity failures. Extend `scripts/load_social_mood.py` with an activity workload (J-02).

## 17. No destructive operations without approval

Hosted SQL, AWS changes, deployments, billable live AI runs and hosted test fixtures all require explicit approval in the implementation session. Local verification uses only `*_test` databases on the disposable container.
