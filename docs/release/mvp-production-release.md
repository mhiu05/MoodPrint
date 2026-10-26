# MoodPrint MVP release evidence

Release date: 2026-10-26, Asia/Bangkok. Operational timestamps below are UTC.

## A. Overall status

**RELEASE_LIMITED — controlled invite-only beta.** The integrated release is deployed and critical live functional/privacy journeys passed at https://moodprint.duckdns.org/. Maintenance is removed, public HTTPS/assets/health pass, and the release timer is active. Signup remains disabled and email confirmation required. All three specified obsolete branches are deleted locally/remotely. Measured latency targets still fail; SMTP delivery, staffed moderation and portable recovery remain unverified. This is not an unrestricted production-readiness claim.

## B. Git integration and verification

Initial remote main: `2c71135e6c8d08b43fabd6621950bcdd530d92ed`. Integration branch: `release/moodprint-mvp-integration`, external worktree `E:/MoodPrint-release-integration`.

| Source | Verified tip | Integration |
|---|---|---|
|docs/productization-plan|8297e64b916a1f71939fe399601d2bee528bc1b3|Merge first, retaining16 commits absent from local-MVP|
|fix/moodprint-local-mvp|3a6367021b925c7a6e662aaef1b3c5dc043993ea|Merge second with ordinary ort|
|feat/moodprint-product-experience|e5c8929336be7ff7a362f31b06162735d7e83a05|Already an ancestor of local-MVP; preserved through it|

No textual conflicts or blanket ours/theirs resolution. Retained deployment provenance, shared readiness revision gates and real-provider/history behavior. See [integration decisions](integration-conflicts.md). No manual `.gitignore` edit; existing source-branch changes arrived through Git history.

[PR11](https://github.com/mhiu05/MoodPrint/pull/11) merged as `cfc3a11c7b63a51b4f03832f795e44f591991605`. Main CI caught transient dialog contrast during the opacity animation and correctly prevented publishing. [PR12](https://github.com/mhiu05/MoodPrint/pull/12) removed only that fade, retaining slide/reduced-motion behavior and adding an exact-open-frame regression (RED opacity0, GREEN1).

**Final deployed main: `4de7bb1b1c21c50444b80514cf56715a6155be1e`**, tree equal to verified hotfix `c941e0eacb9b7056149cef46eebbeb618872d5da`.

| Commands actually executed | Observed result |
|---|---|
|`uv run ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py`; `uv run mypy app`|PASS;87 typed source files|
|Backend/PostgreSQL `pytest -q`, final main CI|531 PASS in157.45s|
|Focused retrieval regression tests|27 PASS; discovery37 to14 SQL statements; v1/shadow goal race covered|
|`npm run typecheck`; `npm test`; `npm run build`; `npm audit --audit-level=low`|PASS;54 unit tests;0 vulnerabilities|
|OpenAPI export; `npm run contracts:generate`|No semantic drift|
|`npm run test:e2e`|63 PASS; mocked APIs, separately identified|
|`scripts/test_fullstack.py`|26 PASS for v1 and26 PASS explicit v2 locally;26 PASS in final main CI, synthetic provider/auth|
|Focused activity/contrast full-stack journeys|3 PASS|
|`alembic upgrade head`; `alembic check` on disposable PostgreSQL|0014; no new upgrade operations|
|Linux `python -m unittest discover -s deploy/aws/tests -q`|14 PASS; native Windows attempt fails on Linux-only fcntl|
|API/web Docker builds; Compose validation|PASS|
|[Main CI40245721736](https://github.com/mhiu05/MoodPrint/actions/runs/40245721736)|SUCCESS on exact final SHA|
|[Publish40246469472](https://github.com/mhiu05/MoodPrint/actions/runs/40246469472)|SUCCESS; pinned images and provenance|

Earlier failures retained: local discovery timing, transient CI timing outlier, Windows socket10055 in one v2 run, dialog contrast. Subsequent focused/full verification passed without weakening assertions or thresholds. Optimized discovery measured51-84ms in diagnostic contexts. GC pauses were observed elsewhere; the exact original CI outlier cause is unproven. A separate reviewer diagnostic run had530 PASS/1 pre-existing-role failure and is not counted as release-suite success.

## C. Hosted Supabase

Exact project `roznanxbiyqybjpvtilq`, database `postgres`, schema `moodprint`; TLS and migration identity verified. Initial `0010_account_deletion` -> **`0014_moderation`**. Supabase remains Tokyo; AWS remains Sydney. No Region migration.

Fresh pre-DDL repeatable-read snapshot190228Z passed decrypt/list/isolated restore with32 exact counts/385 rows. Each reviewed offline SQL upgrade was rehearsed on that snapshot, then applied to the hosted target in its reviewed transaction. No blind stamp, online Alembic or reset.

| Upgrade | Reviewed Windows raw SQL SHA256 (CRLF) | Hosted result |
|---|---|---|
|0011|4d5e485f2305e21935255a7e3c07017cc43d9ceb81f288feb601f038baf9363f|PASS|
|0012|608c82109251d38fb05e903b86a7cf751dcde5b0ba0797c4ea9fa023f7b17489|PASS|
|0013|6176dd5bd3160654bd8789c96e68924a45b99f7803e4c58c072cbec786e93464|PASS|
|0014|1e0048215a0a3097840bb155b4fbebac30ec4d2b38190fbd90b8b56e548e7837|PASS|

Git canonical LF hashes differ. The reviewed script normalizes only line endings and compares the exact Alembic export. Reports: `docs/productization/migrations/0011-execution.json` through `0014-execution.json`.

All385 existing rows preserved;39 tables/39 RLS;0 invalid constraints; Auth structure unchanged. Runtime role has application DML, no schema/revision mutation or RLS bypass. Supabase API roles cannot directly read application tables. The migration-owner URL found in the prior runtime was removed before deployment; new-container inspection confirms it is absent. No service-role key added.

Fresh pre-deployment backup `20261025T234120Z`:39 exact table counts/385 rows,174916 plaintext bytes, decrypt/list/restore PASS. Protected file: `C:/Users/minhh/moodprint-backups/moodprint-release-20261025T234120Z.dump.dpapi`. Plaintext SHA256 `f8412b9861c47b70f317459a2506eb69aadd4ac0cb3bf7b6d6d9c46d586ff155`; encrypted SHA256 `71335fd41fe7168c990c5bcaa2b9ab0585499fb1e0d3273d82d7bb2218cf7c39`. Windows CurrentUser DPAPI/private ACL, outside Git. No Auth row data copied. Independent portable recovery/PITR is unverified; recovery requires this Windows profile.

## D. AWS and rollback

Existing t3.small EC2 `i-0664d6ea5930452db`, **ap-southeast-2**, FREE/ACTIVE project plan. No paid upgrade or new persistent AWS resources. Existing GitHub CI/publish/release pipeline, verified poller, GHCR digest pins and SSM used. Finalization00:34:06-00:34:12 removed maintenance and enabled/started the release timer: active. Both exact image containers are healthy with restart count0. The compatible rollback Compose config validates. SSM evidence: `2b7d312a-1c82-4e6f-a5e9-b910e858f76e`.

[Published release](https://github.com/mhiu05/MoodPrint/releases/tag/staging-4de7bb1b1c21c50444b80514cf56715a6155be1e):

| Component | Deployed image |
|---|---|
|API|`ghcr.io/mhiu05/moodprint-api@sha256:6ce3beb9facd8e4e22229b268e403b0b1678d2efba51c88db57286b5d5568879`|
|Web|`ghcr.io/mhiu05/moodprint-web@sha256:1524bb7688d179d74d67dfc0ff98d29796150ca2998fa482f82fdc7ed8982f4f`|

Both containers/domain readiness healthy after deployment. Initial core acceptance used v1 scorer/activities off. Root-only compatible config/runtime were preserved at00:06:07 as `/opt/moodprint/staging.compatible-mvp.env` and `/opt/moodprint/runtime.compatible-mvp.env`. SSM runtime version6 then enabled v2/activities. Command `d53401c2-32c2-4e4c-b876-8725fd0ee5eb` redeployed the SAME images00:06:24-00:06:45, actually recreating API. Real saved-history continuation passed afterward.

Final intended flags: AI/history/semantic/accounting on; matching v2; icebreaker/coop_quiz/focus on; sandbox/STT/moderation-admin off. USD1/day observed-spend guard,60 AI turns/user/day,global concurrency10. Observed-spend guard is not a strict provider-billing cap. Secrets stay backend-only.

Historical image2c is unsafe after new-format writes: old profile validation, room gates and privacy workers cannot handle all new data. Never restart old2c workers or downgrade schema. Recovery:

1. Enable `python3 /opt/moodprint/release_gate.py enable`, stop poller timer and quiesce API.
2. Inspect/preserve current state. Restore the verified root-only compatible config/runtime retaining0014 and exact4de images. Also restore matching v1/activities-off in SSM so a later deploy cannot silently undo recovery. Validate Compose and health before lifting maintenance.
3. Prefer a tested forward repair. Database restore requires separate reconciliation; no automatic data/schema rollback was attempted.

Baseline core behavior and preservation verified; no hosted failure-injection rollback was performed.

## E. Real-domain verification

Two independently authenticated, explicitly configured synthetic fixtures; no HTTP mocks, copied cookies or destructive hosted harness. Exact subjects/emails checked privately; third application user untouched.

| Journey | Result |
|---|---|
|Hosted login; independent cookies|PASS; HttpOnly/Secure/SameSite Strict|
|Mây/Gương/Nhịp/Rủ Rê/Cầu Nối real replies/SSE|PASS, all five|
|Five saved chats/reload/peer denial|PASS; peer404|
|Logout/login and actual API restart continuation|PASS; real model recalled original marker in both cases|
|Real memory proposal/edited approval/persistence/isolation|PASS; explicit approval, owner-only|
|Real assistant reads approved memory|PASS|
|Voyage semantic retrieval|PASS; actual1024-dimension index and counted real query returned owned approved memory|
|AI cancellation/explicit recovery|PASS; no automatic replay|
|Mood write/list/summary|PASS; new synthetic date, no overwritten entry|
|v2 publication/explanations/mutual acceptance|PASS|
|Human messages/unread/read/refresh|PASS|
|Icebreaker three rounds/hidden responses|PASS|
|Quiz five rounds/hidden correct answers|PASS|
|Shared Focus invite/pause/reload/peer resume/completion|PASS;15 actual production-timer minutes together, both users completed|
|Owner export/peer denial/peer-content exclusion/one-shot download|PASS|
|Blocking and peer-room access revocation|PASS; peer403|
|Synthetic abuse report/admin gate|PASS; labeled synthetic report, authenticated admin404 while disabled|
|Fixture privacy cleanup|PASS; profiles withdrawn, MATCH off,5 new conversations erased, new memory/vector/mood removed, original AI/MEM/history/semantic choices restored|
|Fresh cleanup-session logout/revocation|PASS; both subsequent session requests401|
|Final public ingress without release header|PASS00:34:20; root/assets/live/ready200, unauthenticated session401, HTTP308 to verified HTTPS|

Harness failures are retained: corrupted bot label stopped core after successful cancellation; scoped resume finished without replaying initial provider journeys. Social initially read unreadCount from room detail (default0); corrected to the authoritative inbox-list endpoint and resumed the same room. Cleanup initially expected404 after deletion; the documented expired/removed-conversation response is410, so cleanup resumed by listing only remaining owned conversations. A semantic probe initially used a Windows-mangled query; the corrected query passed. AWS CLI output encoding also made one earlier probe submission ambiguous, so the successful one-query assertion is not a count of all embedding probes. None of these harness corrections required an application patch.

Scoped five-conversation accounting:10 turns,9 complete/1 cancelled;10 requests/10 responses,all10 settled;10916 input tokens (1187 cached),722 output,1 tool call; estimatedUSD0.00134577 under configured pricing snapshot. Not a provider invoice; separate embedding/provider probes excluded. Script caps AI turns at12; no model load testing.

## F. UX/UI

Actual390/430/768/1440 reflow, keyboard focus and reduced-motion checks PASS; axe WCAG2A/2AA/2.1AA PASS for assistants/self/memory/settings at390/1440. Screenshots outside Git: `E:/MoodPrint-release-evidence/ai-history-desktop.png`, `domain-390.png`, `domain-430.png`, `domain-768.png`, `domain-1440.png`, `icebreaker-completed.png`, `coop_quiz-completed.png`, `focus-running-mobile.png`, `focus-completed.png`. Desktop AI,390 settings, desktop Icebreaker and mobile Quiz/Focus captures visually inspected. The Focus running capture records the deliberately paused state before the resume request completed; subsequent server checks confirmed active and completed. Dialog entrance contrast fixed; integrated product-experience improvements retained.

## G. Performance

Unchanged read/write targets500/800ms. Actual-domain readiness baseline from operator workstation:10 sequential requests,p50 873ms,p95 1605.7ms,0 errors. Includes external network/hosted DB; not authenticated multi-user capacity.

Isolated bounded load on existing EC2 used exact integrated source, identical locked production dependencies, one API worker and disposable local PostgreSQL. API+driver shared1.5CPU; PostgreSQL0.5CPU. No hosted Auth/DB or model calls. Do not interpret as50 real hosted users.

| Users | Requests | Elapsed | Throughput | p95 failures | Verdict |
|---|---:|---:|---:|---|---|
|10|670|22.15s|30.2req/s|session519.1ms|FAIL latency|
|20|1326|32.91s|40.3req/s|candidates674.9ms;session788.2ms|FAIL latency|
|50|3336|80.75s|41.3req/s|candidates3030.1ms;send2283.7ms;activity-ready1578.4ms|FAIL latency|

All:0 unexpected statuses,0 flow exceptions,0 integrity failures,pool peak12. At50:API77.258CPU-seconds/80.75wall,51967 SQL statements,620.307s summed overlapping SQL time. Workload CPU peak137.19% includes driver; PostgreSQL27.56%. Throughput plateau40->41req/s, API CPU and bounded pool show a capacity limitation in this topology. No threshold changes. Test containers removed/results retained. Multiple workers require delivery/fencing redesign.

Authenticated actual-domain measurement at00:14-00:16 used12 sequential samples per operation, concurrency1, no model calls, while two real browsers exercised activities. Collection completed with0 errors; **latency gate FAIL** for every operation against unchanged500ms read target. Per-operation throughput is sequential throughput, not server capacity.

| Operation | p50 ms | p95 ms | Sequential req/s | Errors |
|---|---:|---:|---:|---:|
|session|2058.6|2774.2|0.47|0|
|candidates|2656.9|3183.1|0.37|0|
|messages|2517.1|2736.7|0.39|0|
|activity current|2878.4|3485.6|0.34|0|

Actual production resource sampling00:14:05-00:17:30,18 samples:API CPU median6.975%,peak43.57%;memory152 to168.5MiB of768MiB limit;host available memory minimum1122.8MiB. This two-fixture window did not saturate CPU/RAM. A separate warm `select1` probe from the actual API container to hosted PostgreSQL measured12 samples,p50 114.5ms,p95 114.7ms,0 errors. This proves material per-statement round-trip cost; it does not isolate every contributor to endpoint latency. The isolated50-user CPU bottleneck and the hosted two-user network/query overhead are different measurements.

Next work: batch authorization/consent reads without weakening session/consent fences, reduce polling/query demand, measure with an external driver and investigate Sydney-Tokyo DB placement before promising capacity or purchasing resources.

## H. Security/reliability

Consent/edited memory approval/peer denial/secure cookies and CSRF-protected API exercised. Only exact fixture subjects may be cleaned up. Narrow identity-checking helper cleared their prior pair block/cooldown; no mass cleanup or legitimate user consent/data changes.

Post-cleanup server assertions confirm all3 application users preserved; fixture profiles withdrawn/MATCH disabled; all5 new conversations absent; new memory and vector removed; all3 activity rows completed. Only newly created AI/memory/mood items were deleted. Synthetic human-message/activity/report audit records remain under normal retention; existing fixture accounts were not deleted. Fresh cleanup sessions were logged out; earlier closed-browser sessions expire normally, so this is not a claim of global historical-session revocation. A's original AI/MEM/history/semantic preferences were restored; B's AI/MEM were unchanged. Both fixture profiles remain withdrawn and MATCH off to avoid mixing with real users.

The owned local raw-snapshot Docker container `moodprint-release-pg` and its verified exclusive anonymous volume were stopped/removed after restore evidence and encrypted-backup hash verification. The existing user container was preserved. No production database reset or destructive account test occurred.

Authoritative Auth settings: `disable_signup=true`, `mailer_autoconfirm=false`, anonymous sign-in off. Email confirmation retained. Earlier UI save appeared reverted after several hours; re-saved and API-verified before deployment. Screenshot: `E:/MoodPrint-release-evidence/invite-only-supabase.png`. SMTP delivery unverified; authorized staff0, moderation-admin stays off. No legal/privacy sign-off implied.

Supabase advisor: leaked-password protection disabled (WARN),5 unindexed foreign keys/33 unused indexes (INFO), no RLS warning. Portable recovery/PITR and staffed incident response unverified. Keep access restricted.

## I. Git cleanup

After critical live acceptance and public-health verification, fresh fetch/ancestry checks found no unique source commits and no open PR requiring these branches. Normal `git push origin --delete` and `git branch -d` deleted exactly:

| Branch | Local | Remote |
|---|---|---|
|docs/productization-plan|DELETED|DELETED|
|feat/moodprint-product-experience|DELETED|DELETED|
|fix/moodprint-local-mvp|DELETED|DELETED|

Root checkout is now main at4de7bb1; its private backend environment is byte-for-byte preserved. Both original source worktrees remain at their original paths, detached at their integrated commits, preserving ignored caches/dependencies/debug artifacts. No force removal, other branch deletion, tag deletion or release deletion. Root's untracked `.worktrees/` remains intentional; `.gitignore` was not manually edited. The two extra empty untracked directories observed during preflight were preserved too.

Fresh GitHub API inspection shows PR9 already closed/marked merged at2026-10-25T19:08:19Z, immediately after PR11. Its commits entered main through the reviewed integration merge (intermediate merge681049c); no separate outdated-PR merge occurred. [Final explanation posted](https://github.com/mhiu05/MoodPrint/pull/9#issuecomment-6405606093). Connector comment permission was403, so the authorized existing GitHub CLI posted it. No reopening or remerge.

Final report/evidence are preserved on `release/moodprint-mvp-integration` after fast-forwarding it to the released main before the documentation commit. This evidence-only commit is intentionally separate from deployed application main4de7bb1, avoiding a documentation-triggered replacement application release. The main branch's earlier report is an intermediate snapshot; this report supersedes it.

## J. Outstanding items

| Priority | Item | Handling |
|---|---|---|
|P0|No demonstrated unresolved P0 in exercised journeys|Critical functional/privacy acceptance passed|
|P1|Measured latency failure, hosted50-user capacity unproven|Restricted access; failed metrics retained|
|P1|SMTP/staffed moderation unverified|Signup/admin off, invite-only scope|
|P2|Portable recovery/PITR, leaked-password protection, index review|Operator follow-up|

## K. Recommendation and timeline

**Recommend controlled invite-only beta, not unrestricted public use.** Functional release/deployment/cleanup objectives are complete. Capacity, SMTP/staffed moderation and recovery limits remain explicit; no failing latency gate was waived or relabeled PASS. Do not invite a larger cohort until those operational requirements are resolved.

| UTC evidence | System change |
|---|---|
|2026-10-25 snapshot190228Z|Backup/restore/rehearsal before hosted0011-0014|
|PR11 then failed main CI|Integration merged; dialog failure prevented publication|
|PR12/main CI40245721736|Contrast fixed; final main gates passed|
|2026-10-25T23:41:20|Fresh0014 backup,39 exact counts/385 rows|
|Publish40246469472|Attested4de digest pair released|
|SSM0fd7790c-638b-4c71-af18-f14b84669c45|Gate and compatible baseline deployed, healthy|
|23:57-00:05|Five real assistants/history/memory/cancel/mood/responsive acceptance|
|2026-10-26T00:06:07|Compatible runtime/config preserved|
|00:06:24-00:06:45|Runtime6, same images/API recreated,v2/activities on|
|00:07:49|Real history continuation after restart PASS|
|00:08:52|v2 matching/mutual approval PASS|
|00:10:57|Two-user messages/unread/read/refresh PASS|
|00:12:05|Three-round Icebreaker PASS|
|00:13:55|Five-round Quiz PASS|
|00:14:33|Focus pause/reload/peer resume PASS|
|00:16:31|Actual-domain authenticated latency collected;500ms gates FAIL|
|00:17:11|Scoped export/peer exclusion/one-shot download PASS|
|00:29:56|Full15-minute Focus completion confirmed by both users|
|00:30:01-00:30:07|Block/access revocation/report/admin-off PASS|
|00:33:40-00:33:43|Scoped fixture deletion/preferences restoration/logout PASS|
|00:34:06-00:34:12|Server privacy assertions, maintenance removal and timer active; images healthy|
|00:34:20|Public HTTPS/root/assets/health PASS without tester header|
|After final public acceptance|Exactly3 local/remote source branches deleted; PR9 explanation posted|

Live commands executed from the backend virtual environment: `python E:/MoodPrint-release-run-live.py core`, `core-resume`, `restart`, `social`, `social-resume`, `metrics`, `privacy`, `cleanup`, `cleanup-resume` (one mode per invocation). The original failed harness runs and successful scoped resumes are retained separately. Operational runners: `python E:/MoodPrint-release-ssm.py <reviewed-shell-file> <evidence-label>`, `python E:/MoodPrint-release-public-final.py`, `python E:/MoodPrint-release-clean-branches.py`; final `scripts/check_plans.py` and `git diff --check` passed. These operational scripts remain outside Git alongside the raw release evidence; they are not automatic production test hooks.

Portable non-secret evidence: [release evidence directory](evidence/2026-10-26/). Raw browser screenshots/logs remain at `E:/MoodPrint-release-evidence/`; protected backups/fixture metadata stay outside Git. No credentials, cookies or private real-user content included.
