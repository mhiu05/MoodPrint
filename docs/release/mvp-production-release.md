# MoodPrint MVP production release

Release date: 2026-10-26, Asia/Bangkok. **Current verdict: HOLD (verification and rollout in progress).**

## Initial state and integration

`origin/main` was `2c71135e6c8d08b43fabd6621950bcdd530d92ed`. The original checkout and two development worktrees were preserved. Integration worktree: `E:/MoodPrint-release-integration`; branch: `release/moodprint-mvp-integration`; draft PR [#11](https://github.com/mhiu05/MoodPrint/pull/11).

Productization `8297e64` had 16 commits absent from local-MVP. Merge it first, then local-MVP `3a63670`, which includes product-experience `e5c8929`. Both merges used ordinary ort without textual conflicts. See [integration decisions](integration-conflicts.md). Existing draft PR #9 remains open pending successful replacement release. No obsolete branch has been deleted.

## Verification ledger

| Scope | Command actually executed | Observed result |
|---|---|---|
| Backend static | `uv run --locked ruff check app tests evals alembic` plus CI script list; `uv run --locked mypy app` | Ruff passes; mypy passes, 87 source files |
| Backend/PostgreSQL | `pytest -q`, separate `release_backend_test` | 524 passed, one performance failure: matching50-peer maximum 841ms against600ms threshold, during concurrent local verification. Targeted investigation pending; threshold unchanged |
| Frontend | `npm ci`; `npm run typecheck`; `npm test`; `npm run build`; `npm audit --audit-level=low` | 54 tests pass; typecheck/build pass; zero audit vulnerabilities |
| API contracts | `export_openapi.py`; `npm run contracts:generate`; `git diff --exit-code` for both artifacts | No semantic contract drift |
| Browser/mocked API | `npm run test:e2e` | 62 pass; these do not establish hosted behavior |
| Full stack/synthetic provider | `test_fullstack.py` | Default v1:26 pass. Explicit v2 run in progress. Real local PostgreSQL and HTTP, synthetic authentication/model |
| Migration chain | `alembic upgrade head`; `alembic check` on disposable database | Through0014; no new upgrade operations |
| Release poller | `python -m unittest discover -s deploy/aws/tests -q` in Linux Python3.12 container | 12 pass; direct Windows invocation fails because fcntl is Linux-specific |
| Packaging | `docker build --platform linux/amd64` for backend/frontend | Both images build |
| GitHub CI | Push run [40221356595](https://github.com/mhiu05/MoodPrint/actions/runs/40221356595) | Pass on d4e2a29 |
| GitHub PR CI | Run [40221475773](https://github.com/mhiu05/MoodPrint/actions/runs/40221475773) | Failed a starter assertion: peer's empty-state button was mistaken for a persisted message. Test now waits for peer readiness and asserts zero message rows plus an empty real message API response. Reverification pending |

No failing check is waived. Historical provider results in other documents are not fresh release acceptance.

## Hosted Supabase safeguards

Exact project: `roznanxbiyqybjpvtilq`, database `postgres`, schema `moodprint`, TLS verified, migration identity `postgres`, configured owner pooler endpoint verified. Initial revision `0010_account_deletion`;32 tables with RLS. Runtime/application roles are nonsuperuser and have no RLS bypass. No concurrent schema operation observed.

Fresh logical snapshot uses an exported repeatable-read snapshot, including exact table counts from that snapshot. Private user ACL and Windows CurrentUser DPAPI protect the backup outside Git. Backup `20261025T183149Z`:146218 plaintext bytes; SHA256 `ba702e3027794289ada94dcedacf8591d7a3f263b0d5c4a429a81923d4c2b429`. Decrypt round trip, archive listing and isolated pg_restore all pass; all32 table counts/385 total rows match. No Auth data was copied. Recovery requires this Windows user profile; this is not independently portable PITR coverage.

All four exact reviewed SQL artifacts were rehearsed on that restored snapshot through `apply_supabase_review.py --upgrade <revision> --rehearse-url <local *_test>`. All passed revision, row preservation, RLS, policies, runtime grants, API-role denial and unchanged Auth structure. Current Windows-checkout raw-byte hashes (CRLF; the script separately normalizes and compares the exact Alembic export):

| Revision | SHA256 |
|---|---|
|0011|`4d5e485f2305e21935255a7e3c07017cc43d9ceb81f288feb601f038baf9363f`|
|0012|`608c82109251d38fb05e903b86a7cf751dcde5b0ba0797c4ea9fa023f7b17489`|
|0013|`6176dd5bd3160654bd8789c96e68924a45b99f7803e4c58c072cbec786e93464`|
|0014|`1e0048215a0a3097840bb155b4fbebac30ec4d2b38190fbd90b8b56e548e7837`|

Hosted DDL has not yet been executed. Schema drift comparison and remaining release gates precede it.

## AWS and safe rollout ordering

Existing EC2 `i-0664d6ea5930452db`, t3.small, SSM online, Region `ap-southeast-2`. AWS profile refreshed with user approval. Plan:FREE/ACTIVE. No replacement infrastructure provisioned.

Initial healthy release SHA:`2c71135e6c8d08b43fabd6621950bcdd530d92ed`.

- API:`ghcr.io/mhiu05/moodprint-api@sha256:50e204263d25311ee6d0a63cbb3c80e2e4fe7864776d07d738fa591e65ec9bf3`.
- Web:`ghcr.io/mhiu05/moodprint-web@sha256:0cfabd49ad0b486e83ebbb82a9196de3e77d9c7150c565f6e0c03eeac2a2492f`.

Previous images for dad0cb4 are recorded in staging.previous.env. These historical images are not valid full rollback after v2/activity writes: old profile validation rejects new fields; old room gates reject retained rooms; old privacy workers cannot erase new activity data. Readiness acceptance is insufficient. Review reproduced the validation failure. The rollback guide was corrected.

Controlled sequence:

1. Stop release-poller timer temporarily; preserve active images and root-only runtime backup.
2. Rehearse and apply only missing reviewed migrations, retaining old behavior until new data can be safely handled.
3. During the initial image transition, block application writes at the proxy. Merge only after all gates pass.
4. Publish/deploy integrated image with `MATCHING_SCORER=v1` (serves rules-v1.1), activities off; verify core behavior and preserve this compatible image/runtime as the rollback baseline.
5. Enable v2/activities using that same verified image. Revert to the compatible baseline if validation fails. Resume the poller after the controlled rollout.
6. Never start old image2c workers after new-format writes. Emergency recovery must stop the API and serve maintenance until a compatible forward repair is ready; no schema downgrade.

SSM runtime version1 was backed up mode0600 on EC2. Instance role correctly denied PutParameter; no update occurred through that role. The authorized operator profile then prepared version2:AI/history/accounting true; daily estimated-spend admission threshold USD1;60 turns/user/day;global concurrency10;scorer v1;activities false;all three kinds configured;moderation-admin/semantic/STT/sandbox false. Final v2/activities enablement is pending. Provider secrets were never printed or committed. The budget tracks observed estimated spend and can overshoot for in-flight or uncertain calls; it is not a strict billing cap.

## Public domain, provider and user journeys

Acceptance target:[moodprint.duckdns.org](https://moodprint.duckdns.org/). Initial old-release checks:HTTP200,TLS verification0,liveness ok,readiness ready. Both containers healthy. Initial resource sample:API136MiB,web14MiB,1217MiB RAM available,disk14%; this is not a load measurement.

Two configured synthetic hosted identities were checked privately against their configured Auth subjects/emails; both match. Three application users exist, so testing must isolate the fixture pair from the other user and withdraw test profiles before restoring access.

Supabase public signup was disabled through the existing authenticated dashboard, with confirmation-email protection retained. The connected Supabase tools do not expose Auth configuration writes, so this setting used the browser. Screenshot saved outside Git. SMTP delivery and a staffed moderation operator are unverified; release remains invite-only. No consent was granted to real users.

| Candidate domain acceptance | Current status |
|---|---|
|Real authentication/cookies|Pending new deployment|
|Five real AI assistants/streaming/recovery|Pending|
|History reload/logout-login/continue|Pending|
|Approved memory/semantic retrieval|Pending;semantic disabled until verified|
|Mood/insights/export/deletion|Pending|
|Matchingv2/v1.1 fallback|Pending domain evidence|
|Two-account messaging/unread/privacy|Pending|
|Icebreaker/Quiz/Shared Focus|Pending|
|390/430/tablet/desktop,keyboard,reduced-motion|Local coverage passes;candidate domain pending|
|Bounded deployment-like performance|Pending;no live p50/p95/throughput claims|

## Timeline and remaining gates

Observed order:reference fetch→two merges→draft PR11→AWS login→read-only infrastructure/DB checks→fresh encrypted backup/restore→four local rehearsals→Supabase signup restriction→temporary poller stop→operator-prepared SSM compatibility config. No main merge or application rollout yet.

P1 gates:resolve flaky CI assertion and local latency failure;complete final CI/v2 run;verify schema drift;execute hosted migration safely;establish compatible rollback;verify real-domain journeys and bounded capacity. Public-launch gaps:SMTP delivery,staffed moderation,portable backup recovery and actual provider acceptance. Branch deletion and PR9 closure remain prohibited until successful critical live acceptance.

Final main merge SHA,final hosted revision,image digests,live screenshots/performance,issues fixed and cleanup results will be recorded after execution. Current recommendation:HOLD rollout;preserve existing healthy service while gates are completed.
