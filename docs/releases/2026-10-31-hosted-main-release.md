# Hosted main release audit — 2026-10-31

**Verdict: `BLOCKED_OWNER_APPROVAL`**

This is a pre-release audit, not a release-success claim. No hosted database,
AWS, release-hold, image-publication, or deployment mutation was made.

## Source and workflow state

| Item | Verified result |
| --- | --- |
| Target `origin/main` SHA | `cac5548f305aaaa7d3e604b0a8eb4c448f2f4075` |
| Local worktree before this evidence change | Clean; no user changes overwritten |
| Open repository PRs | None |
| Target-SHA verification CI | [Run 41213827545](https://github.com/mhiu05/MoodPrint/actions/runs/41213827545), SUCCESS |
| CI coverage | Disposable PostgreSQL backend checks; migration chain and synthetic load; frontend/contracts; synthetic full stack; reviewed SQL; docs; poller; workflow syntax; Compose and production image builds |
| Target-SHA publication workflow | [Run 41215740094](https://github.com/mhiu05/MoodPrint/actions/runs/41215740094), overall SUCCESS with publication held |
| Hold decision | `deploy/guest-experience.release-hold` is present at target SHA; the hold check passed, exact-main validation was skipped, and build, publish-gate, and publish jobs were skipped |
| SHA-specific staging release / image digests | No `staging-cac5548f305aaaa7d3e604b0a8eb4c448f2f4075` release exists; no images were built or published, so no digests exist |
| Release PR | None created; repository instructions require the hosted, owner, and manual gates to be satisfied first |

The release path is:

```text
verified main CI → publication-hold check → exact-SHA build and GHCR attestations
→ SHA release manifest → EC2 poller verification → Docker Compose image switch
→ HTTPS readiness → hosted user-flow validation
```

The critical path is owner-approved non-production target and migration scope →
verified hosted backup and restore → coordinated compatible 0020 migration and
release preparation → release-hold removal through its separately reviewed PR
→ CI/publication → poller deployment → direct hosted validation. The poller does
not run migrations.

## Hosted application and infrastructure observations

| Check | Result |
| --- | --- |
| Website `/` | HTTP 200 |
| `/api/v1/health/live` | HTTP 200, `{"status":"ok"}` |
| `/api/v1/health/ready` | HTTP 200, `{"status":"ready"}` |
| Current deployed application SHA and image digests | Not freshly verified; the public health endpoints do not identify artifacts |
| Previous hosted SHA | The October 31 migration dossier records `5d2b384516b9318e6ee132c1a8b08dcbc374b79b`; this audit could not re-verify it against EC2 |
| AWS staging instance, Compose/Caddy state, and logs | Not verified: local AWS CLI session is expired, so no authenticated AWS read was possible |
| GitHub workflow/poller effect | Current SHA has no published release manifest; the current poller therefore has no target artifact to deploy |

The site and health checks are reachable, but they do not prove which release
serves them. No sign-in, guest, AI, journal, media, profile, or matching flow was
tested against hosted accounts. The D04 hosted Auth test is intentionally blocked
without an approved non-production target.

## Supabase target and migration 0020

The connected Supabase account exposes project `roznanxbiyqybjpvtilq` (project
name `database`, region `ap-northeast-1`, status `ACTIVE_HEALTHY`). Repository
deployment documentation describes Supabase as the production database. Neither
the project metadata nor the available AWS session establishes that this is an
owner-authorized, staging-only database. It is therefore **not approved as a
destructive migration target**. The project ID is recorded for identification;
no credentials or keys are included.

Read-only SQL inspection confirmed:

| Integrity check | Observed |
| --- | ---: |
| Application schema revision | `0019_journal` |
| `moodprint.users` rows | 6 |
| `moodprint.journal_entries` rows | 0 |
| `moodprint.private_items` rows | 11 across 3 owners |
| Private-item memory proposals | 0 |
| Pending source-backed memory proposals | 0 |
| Proposals with source references | 0 |
| Memories with source references | 0 |

Migration `0020_private_profile_retirement` depends on `0019_journal`. Its SQL
increments `data_version` for the 3 affected owners, deletes the 11
`private_items` rows, expires matching pending source-backed proposals (0
observed), detaches source references (0 observed), then drops the private-items
table and source/purpose columns, constraints, and indexes from memory tables.
It does not delete user accounts or journal rows. It does not change RLS
policies. Its downgrade deliberately raises an error; it is forward-only. The
existing serving backend recorded by the migration dossier only accepts revision
0019, so it cannot safely serve after 0020. No hosted mutation was attempted.

The repository has a successful synthetic archive/restore and migration
rehearsal, but no verified hosted backup, isolated hosted restore, or approved
recovery procedure for this target. Those synthetic results do not protect
hosted user data. Blind database rollback to 0019 is unsafe; a previous 0019-only
backend is also incompatible with a database after 0020. A compatible forward
recovery artifact and coordinated maintenance window are required.

Current Supabase advisories returned one Auth warning (leaked-password
protection disabled) and performance notices for six unindexed foreign keys and
23 unused indexes. No schema change or advisory remediation was performed.

## D01–D04 and manual gates

| Gate | Status | Exact unresolved decision/evidence |
| --- | --- | --- |
| D01 — deletion and retention promise | Owner decision open | Approve the public active-store deletion and backup/provider/log exceptions disclosure, the cleanup operating targets, and the proposed short-lived anti-abuse/cost-counter retention. The current proposal is cleanup start within 60 seconds and completion within 5 minutes when healthy, HMAC counter retention up to 24 hours, and detached daily cost totals for 30 days. |
| D02 — guest operating spend | Owner decision open | Choose a positive daily guest budget in USD and authorize the relevant paid provider(s). No cap is configured; paid guest AI/STT/embedding and real-model tests remain disabled. |
| D03 — feedback retention | Owner decision open | Approve or specify the separate disclosure and retention period for voluntary unlinked feedback. The proposed period is 180 days; collection is disabled. |
| D04 — hosted Auth target | Owner decision open | Name and approve a non-production Auth/database/CAPTCHA target for the synthetic signup, cascade, session, grants, and burst tests. The connected project is not presumed safe for destructive tests. |
| Manual accessibility/device review | Incomplete | Assistive-technology, text zoom, microphone, and hosted CAPTCHA checks remain manual/external gates. |
| Hosted data recovery | Incomplete | Fresh protected backup, integrity check, isolated restore, and recovery rehearsal are not evidenced for the connected project. |

The latest repository release evidence records all six guest/public rollout
flags off and the paid budget unset; the current hosted runtime values could not
be checked without AWS access. No owner decision is inferred here.

## Release decision

**`BLOCKED_OWNER_APPROVAL`** — the hold is working as designed, but the requested
SHA has no published image or release manifest. D01–D04 remain open. The
connected Supabase project is documented as production and cannot be certified
as a non-production target; the migration's exact destructive effect is now
rechecked, but there is no hosted backup/restore evidence. AWS artifact identity
and server logs also remain unverified because the local AWS session expired.

Resolve the D01–D04 decisions, explicitly authorize the identified non-production
database and the stated 11-row retirement impact, and provide access to verify
AWS staging identity. Then re-run target and recovery checks before any hosted
mutation, and continue through the repository's protected release path.
