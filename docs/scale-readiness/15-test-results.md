# Scale readiness — implementation và kết quả, 05-11-2026

## Current round — execution, verification and handoff

Remote CI follow-up:implementation commit `ed75c4a1` failed the full workflow's
Ruff step with20I001import-order errors ([run](https://github.com/mhiu05/MoodPrint/actions/runs/42027966645)).
The narrower local lint scope missed these. Corrected imports in16files;AST comparison
verifies the imported names/modules and every non-import statement are unchanged.
The exact fullCI Ruff command nowPASS locally. After normalization,the local offline
candidate lane reports **118PASS/2SKIP in10.58s**;this is separate from104DB-backed
regression and does not replace the hosted fullworkflow. FullCI must be read back on
the final branch revision;no greenCI claim yet. [Fix evidence](evidence/round2-ci-import-fix.json).
Expanded localCI checks also found2typing errors:transport variable inferred too
narrowly and Starlette's sync-or-async handler registry type. Explicit transport
base annotation and an Awaitable cast for the already-async installed DomainError
handler fix them without changing runtimepolicy. **Full `mypy app`:PASS,194files**;
exactfullCI RuffPASS;drain/envelope/dispatch/campaign/recovery rerun **74PASS/1SKIP,
10.21s**. These counts overlap earlier lanes and must not be summed.

**NO-GO.** Original41task status remains2DONE/27IN_PROGRESS/7BLOCKED/2FAILED/3DEFERRED.
Latest cloud facts supersede t3.small below:targetalready **running m7i-flex.large**,
SSMcommandSuccess,4serviceshealthy,restart0snapshot,EIP/DNS/TLS/ready200.
Active exposed **postgres migration-owner** credential confirmed by TLS READ ONLY
login;runtimepassword differs. No rotation,deploy,SMTP/DBpolicy/budgetactivation.

| Actual command/lane | Result | Evidence / scope |
|---|---|---|
| `pytest backend/tests/test_scale_polling.py` after tightening query budget | RED4queries>3 | round2-poll-red.log |
| Poll/session/guest-expiration targeted lane |22PASS | round2-poll-green.log;beforewriter-racefix |
| Auth/CAPTCHA/budget/guest/history/privacy/drain/review lane |109PASS,152.73s | round2-regression.log;exact command in execution summary;beforefinalwriterfix |
| `pytest backend/tests/test_scale_budget_queries.py` before financial optimization | RED5statements>1 | round2-budget-red.log |
| Single-snapshot financial+detached guest lane |12PASS,24.77s | round2-budget-green.log |
| Financial/guest/search/usage/campaign/recovery integrated lane |87PASS,58.06s | round2-financial-green.log;beforeadditionalcleanupfaulttests |
| Concurrent providerrevocation while waiting for Userlock | RED:DIDNOTRAISE | round2-lock-revocation-red.log |
| Poll/session/guest-expiration after writerfix |24PASS,36.38s | round2-lock-revocation-green.log;writerscheckproviderafterlock;readpoll3queries,monitor5 |
| Remote item_reference payloads |2RED→GREEN in33PASS/2SKIP envelope/capacity/safety lane | round2-reference-red.log;round2-envelope-green.log;zero count/generation forrejectedrefs |
| Campaign primitive |25PASS | round2-campaign-tests.txt;12processrace/crash;no liveadapter/paidcalls |
| Recovery verifier+launch-failure cleanup |31PASS after9newREDfaultcases | round2-recovery-cleanup-faults.json;integrity/sourcecoverage/hostedrestore keptdistinct |
| Localisolated pg_dump/pg_restore | SYNTHETIC_PASS,3.812s | round2-recovery-rehearsal.json;RLS/uncertainhold/object/config/secretfixturebytes;not actualSupabase/EBSrestore |
| Frontend `npm.cmd run typecheck`;`npm.cmd test` | TypecheckPASS;206Vitest+2NodePASS | round2-frontend-typecheck.log;round2-frontend-unit.log. Initial npm.ps1 blocked by executionpolicy;used npm.cmd withoutpolicychange. |

No unnecessary rerun of successful100distributed/NATsignup or prior25Playwright
cases;frontend source did not change this round. No new full2174-test-suitePASSclaim.
Historical full-suite failure/rechecks below remain explicit.

Load evidence:

- [Diagnostic60](evidence/round2-T4-diagnostic60.json):49/50complete,39.194swall,
  measurement9.194s,1pooltimeout,poolrecentp951599ms,looplagp9534.338ms,
  CPU38.957s,RSS199.5MB;FAILED. Provider-session join alone did not fixload.
- [First900attempt](evidence/round2-T4-soak900.json):945/948complete,524.608swall,
  measurement464.608s,meanparents42.17,peak50parents/SSE/provider,3pooltimeouts,
  poolrecentp951475ms,latencyp50/p95/p9925031/31910/37646ms,CPU523.999s,
  RSS201.1MB;FAILED. Uses singleSQLliability but precedes writer-racefix;not finalsourceproof.
- [Final900attempt](evidence/round2-T4-final900.json), after the writer-racefix:
  **1084/1085complete,FAILED**;548.847swall,488.847smeasurement;meanparents43.08,
  peak50parents/SSE/provider;1pooltimeout;recentwindowp95203ms/max669ms,
  latency23333/28628/30350ms(p50/p95/p99);looplagp9523.061ms/p99144.694ms;
  CPU546.623s,RSS201.3MB. One noncompletedstream stoppedarrivals as designed.
  The900swindow was not achieved. Later source changes only sortimports; no
  equivalent immutable deployment/image proof is claimed. Old reportsscope retained.

Latest integrated regression after all reviewfixes:`pytest test_scale_polling,
test_budget_reservations,test_guest_global_budget,test_search_accounting,
test_bounded_responses,test_recovery_verification,test_paid_campaign` with each
fullpath underbackend/tests: **104PASS,54.74s**
([log](evidence/round2-final-regression.log)). ScopedRuffPASS,mypy4filesPASS,
staged whitespacecheckPASS. Gitleaks staged0findings;wholeindex2falsepositives
(empty exampleCAPTCHAkey and anawaitassignment with nohardcodedliteral), no known
exposed passwordinindex and noforbiddentrackedsecretpaths. No suppressions added.
Globaldocschecker remainsFAILED for22links to previously user-deleted documents;
new12–17links verified separately. Unrelated deletions are notstaged/restored.
Docker Desktop became unavailable after these completed runs. Both owned testDB
cleanup attempts refused on failedinspect;local testcredential files removed,
container cleanup pending localdaemon recovery. No deletion claimed:
[cleanup record](evidence/round2-cleanup.json). Recovery script's earlier isolated
rehearsal cleanup and later31faulttests are separate successful scopes.

All runs are L0/Linux1.25vCPU/1536MiB,oneAPI,pool4+1/timeout10s,fakeSDK/Voyage,
simulated8000/600tokens,real owned PostgreSQL17.10. NOT EC2target-size,realprovider,
multi-agent,Caddy/TLS or input-countHTTP evidence. CPU seconds include work during
measurement/warmup/drain;async profile cumulative times must not be summed.
Bounded flags remainclosed;financial invariant in reportedrun scopes is not a
global all-paid-feature proof. No paidgeneration/judgecalls;campaignremains$3available.

Review found writer snapshotrace and remote-reference validation gap;both reproduced
RED beforefix. Recoverylaunchfailurecleanup also fixed withfaulttests. Review scope
and declineditems are recorded in round2-review.md. No independent hostedsecurity,
livepricing or fullrecovery certification claimed.

Chosen recovery policy:RPO24h/RTO8h planning targets;actualProbackupavailability,
Storageobject restore,KMS/vault recovery,EBSboot andapplicationcutover stillunproven.
Paidbackup/restore/cloudactivation needs exactapproval:[14](14-owner-decisions-required.md).
Executionhandoff:[16](16-work-handoff.md),prompt:[17](17-work-execution-prompt.md).

## Earlier evidence and detailed regression history

**NO-GO.** 41 task chưa hoàn tất: **2 DONE, 27 IN_PROGRESS, 7 BLOCKED, 2 FAILED, 3 DEFERRED**.
Branch `feat/upgrade-user`, baseline `0573af5b50c0584c523e5119755479fcf47fae74`, working tree dirty.
[Ledger41 task](12-implementation-progress.md), [inventory](13-cloud-inventory-redacted.md),
[approval proposals](14-owner-decisions-required.md). Không cộng số test trùng nhau giữa các lượt chạy.

## A. Implementation

- Auth: lifespan HTTP pool bounded64 connections/32keepalive,timeout và Retry-After;
  không chia sẻ bearer/cookie,không replay signup/resend/recovery khi outcome unknown.
  Resend/recovery che các identity-specific errors theo allowlist;SMTP/config/unknown4xx
  thành safe availability failure. Metrics chỉ có operation/status/static category.
- Frontend: synchronous submit lock;429 cooldown theo Retry-After,fields được giữ,
  hết cooldown không tự gửi lại. CAPTCHA vẫn cần token mới theo contract hiện hữu.
- Reset password: verify recovery token → commit local auth-version fence → verify lại
  token → PUT provider → best-effort logout. DB/commit failure:0PUT;remote outcome unknown:
  giữ fence,nonretryable notice hướng dẫn đăng nhập/khôi phục. Có thể logout phiên cũ kể cả
  khi provider từ chối đổi mật khẩu;đây là tradeoff an toàn đã ghi ledger.
- DB: budget đủ API/proactive/maps/overlap/reserve;opt-in SET LOCAL timeout trước row lock;
  503 bounded-wait mapping;pool acquisition metrics.Running saved poll9→6→4queries;
  runtime state/conversation/usage được đọc chung,giữ fresh session/provider/age/consent/
  ownership/data-version/account/turn locks. Không cache quyền giữa các tick.
- AI: global schema/helper hỗ trợ50USD/day;candidate exact-count64k input,1200output,
  tối đa3calls,row hold0.12USD,pricing version mới và legacy2USD giữ nguyên.
  Physical dispatch gate API50/proactive2,queue100 và authorization sau queue;SDK nested
  `Agent.as_tool()` cũng nhận post-queue hook.SSE globalcap100,drain/readiness/new-message guard.
- Retention/account deletion giữ relevant open/uncertain/legacy liabilities,cả khi budget tắt.
  Harness L0 có owned-target/egress/output guards;không reset ledger để làm load pass.

New flags mặc định false;không activate production.Tất cả workflow pooled allocation,
registered Voyage/STT accounting,campaign3USD durable controller,full mixed/fault/network harness,
observability và deployment-fencing/recovery rehearsal chưa hoàn tất. Đây còn là engineering
work,không được quy thành chỉ thiếu owner approval. Source/evidence inventory ở
[current staging manifest](evidence/round2-staging-manifest.json). The older local
delivery-manifest.json includes unpublished raw-profile/workspace paths and is not
part of the shared package; do not require Work to retrieve it.

## B. Capacity

L0 Windows Python3.12.13/PostgreSQL17.10/pgvector0.8.2 và Linux Docker cùng DB disposable.
Một API ASGI process,pool4+1,fake SDK model/Voyage;Linux giới hạn1.25vCPU/1536MiB.
Không phải target EC2/Caddy/TLS/real-model throughput.Exact-count HTTP guard được unit-test
với mock transport,không chạy trong Model override của load.

|Mục tiêu|Sample và kết quả|p50/p95/p99|Resources và giới hạn|
|---|---|---|---|
|1000 registered|1000appusers,1000sessions,4000consent:synthetic integrity PASS|N/A|DB40,288,783B;chưa1000confirmedAuth hoặc90daygrowth|
|100signup/60s distributed|100/100accepted,0unexpectedHTTPerror,fakeAuth/CAPTCHA|16/109/187ms|ASGI peers;không actual accounts/mail;CPU/RSS không sampled|
|100signup/60s cùngNAT|100/100accepted với candidate policy,fakeAuth/CAPTCHA|15/47/78ms|Chưa provider egress/quota/mail confirmation;CPU/RSS không sampled|
|50AIparent turns|Đạt peak50 trong bounded burst;50/50complete|36047/38062/42703ms|RSS199,106,560B;fake provider,không soak/multi-agent proof|
|50SSE|Peak50 ASGI streams cùng parent50|Cùng profile burst ở trên|Không tương đương50 socket/TLS/Caddy/slow readers|
|15minute workload|Linux615/616complete,1failure,stopped419.333s;Windows83/100|Linux30085/40486/43899ms|Linux peak50/50/50,mean40.41,pooltimeout1,CPU416.689s,RSS199,778,304B;chưa900smeasurement|
|AI+background/mixed|Từngpath có regression;fullT6/T7/T8 chưa load-validate|UNKNOWN|Không dùng unit counts để thay mixed capacity evidence|

T1/T2/T3 raw:[T1](evidence/T1-local.json),[T2](evidence/T2-local.json),[T3](evidence/T3-local.json).
Các run sau là những scope riêng,không phải before/after có kiểm soát hoàn toàn:

|Profile|Completed/attempts;status|Peak parent/SSE/provider|Latency p50/p95/p99|Resources|Raw|
|---|---|---|---|---|---|
|Legacy $2 holds|25/50; FAILED|25/25/25|5750/22188/22500 ms|RSS 191,287,296B|[JSON](evidence/T4-local.json)|
|Bounded burst|50/50; FAILED|50/50/48|36047/38062/42703 ms|RSS 199,106,560B|[JSON](evidence/T4-bounded-debug.json)|
|Windows 900s attempt|83/100; FAILED|50/50/50|35000/42797/78391 ms|RSS 201,629,696B; pool timeouts 19, recent p95 6297ms|[JSON](evidence/T4-bounded-soak-2.json)|
|Linux 900s attempt|615/616; FAILED|50/50/50|30085/40486/43899 ms|RSS 199,778,304B; pool timeouts 1, recent p95 1600ms|[JSON](evidence/T4-linux-bounded.json)|
|Actor prefetch,60s|202/202; FAILED|50/50/50|24460/29774/31524 ms|RSS 200,413,184B; pool timeouts 0, recent p95 2738ms|[JSON](evidence/T4-linux-prefetch.json)|
|State join + observer,60s|155/155; FAILED|50/50/50|29338/37039/39811 ms|RSS 199,712,768B; pool timeouts 0, recent p95 1326ms|[JSON](evidence/T4-linux-statejoin.json)|
|Rejected admission width1|37/50; FAILED|37/37/35|19986/32983/33340 ms|RSS 195,207,168B; pool timeouts 0, recent p95 923ms|[JSON](evidence/T4-linux-admission.json)|
|Rejected admission width2|33/50; FAILED|33/33/27|24381/36554/37910 ms|RSS 193,802,240B; pool timeouts 0, recent p95 894ms|[JSON](evidence/T4-linux-admission2.json)|

Actor-prefetch diagnostic202/202 complete nhưng mean43.79<45 và recent pool p952738ms.
State-join run có observer độc lập thêm1PG connection;155/155 complete,mean41.31,pool p951326ms;
profiling thêm overhead và gồm seed/drain nên không coi là controlled performance improvement.
[Wait profile](evidence/T4-wait-profile.json):peak3connections chờ advisory lock,checkout-hold p95145.67ms,
advisory wait max617.48ms,không observer error.[CPU profile](evidence/T4-profile-summary.json) có cả
imports/seed;async cumulative times chồng lấn,không được cộng thành CPU elapsed.

Thử nghiệm HTTP admission queue trước checkout width1/2 lần lượt chỉ nhận37/50 và33/50;
đã **gỡ khỏi candidate**. Giữ evidence thất bại;không nâng deadline/pool để che rejection.
Hiện tại capacity gate vẫn FAILED;không có15-minute PASS đúng source/config hiện hành.

## C. Cloud verification

- AWS account…3536,Sydney:`moodprint-staging` **t3.small**,2vCPU;t3.large là target.
  24hCPU288samples,max39.878%,latest7.870%;credits576,unlimited,surplus/charged0 trong snapshot.
  EBS30GiB gp3 encrypted3000IOPS/125MiB/s;SSMOnline,IMDSv2 required.
  Query prefixMoodPrint trả0alarms;targetvolume0snapshots;không suy ra account không có backup khác.
- SES Essentials vẫn **sandbox**,200recipient/day,1/s.Sau approvalC02a có1Gmail EMAIL_ADDRESS
  identity verified SUCCESS/sendingtrue;domain production chọn sau.Chỉ verification email,
  chưa application confirmation/recovery canary;SMTP/DNS/IAM/runtime không thay đổi.
- Supabase project khớp configured fingerprint:Pro,ACTIVE_HEALTHY,Tokyo,PG17.11,
  server max60/runtime role20,không superuser/BYPASSRLS.Confirmation bật;private bucket50MiB/file,
  6objects aggregate9,473,860B;sample5private tables RLS/no browser SELECT/helper no public EXECUTE.
  ComputeSKU/pooler caps/SMTP/Auth limits/CAPTCHAactual/backupPITR vẫn UNKNOWN.
  Advisor cảnh báo leaked password protection disabled.Sydney↔Tokyo RTT chưa đo từ runtime.
- OpenAI model GET `gpt-6-luna` trả200,không generation.RPM/TPM/accountpricing/spend và exact-count
  endpoint access/fees chưa xác minh.Chrome thấy Supabase tab nhưng đọc trang bị lỗi.
  GitHub main trùng baseline;status/PR-workflow query empty không chứng minh all CI passed;
  dirty local candidate chưa được remote CI kiểm chứng.

[Cloud sources](13-cloud-inventory-redacted.md),[SES C02a](evidence/ses-canary-identity.json),
[GitHub scope](evidence/github-readonly.json). SSM v26 vẫn budget20/global10,không phải proof effective container env.

## D. AI cost và quality

Target global50USD/day đã chuẩn bị,chưa activate.Chưa chứng minh hard cap cho **mọi** paidAI feature.
Workflow pooled allocation chưa có;per-row conservative holds không được mô tả thành pooled accounting.
Campaign tổng3USD: **0generation calls,0USD spent/reserved/unknown,3USD remaining**;
0judged responses,0judge API calls,scoresN/A,chưa quality validation.Không đổi generation model.
Own coding-agent inference không được khẳng định miễn phí.
[Cost](evidence/ai-cost-report.md),[coverage](evidence/ai-test-coverage.md),
[rubric](evidence/ai-evaluation-report.md),[campaign ledger](evidence/ai-generation-results.json).

## E. Tests,security và reliability

|Command/lane|Actual result|Evidence và giới hạn|
|---|---|---|
|Initialfull `pytest -q`|2174PASS,3FAIL,4SKIP;3823.60s|[full](evidence/backend-full.log);older source,không all-green claim|
|Recheck3full-suite failures|16PASS|[recheck](evidence/full-suite-failure-recheck.log);flagcatalog/retention expectation fixed;inbox p9526ms vs567ms under contention|
|Auth/budget/recovery baseline|101PASS|[log](evidence/backend-regression.log)|
|Boundedfinancial/guest/retention|37PASS|[log](evidence/bounded-accounting.log)|
|History/events/poll/recovery|48PASS|[log](evidence/polling-regression.log)|
|V3/collab/group/journal/guest integration|113PASS,2SKIP|[log](evidence/current-integration.log);earlier source|
|Actor prefetch Auth/history/guest/eligibility|82PASS|[log](evidence/poll-prefetch-green-3.log)|
|Runtime-state Auth/history/guest/privacy/recovery|190PASS,616.35s|[log](evidence/runtime-state-regression.log)|
|Reset/unknown/mail/CAPTCHA regression|70PASS|[log](evidence/reset-fence-green.log);3 fault tests RED first|
|Provision flush/commit/view faults|3PASS|[log](evidence/provision-faults.log);no cookies on error,oneUser/fourConsent after retry|
|Expanded candidate before nested-hook fix|136PASS,8FAIL|[log](evidence/candidate-current-regression.log);nested Runner missing fence|
|Nestedhook/SDK/orchestration/fence recheck|39PASS|[log](evidence/nested-hooks-green.log);false/true param case RED first|
|Final current candidate matrix|242 passed in 449.37s (0:07:29)|[log](evidence/final-candidate-regression.log);exact commands below|
|Current frontend typecheck / unit|typecheck exit0;206Vitest+2NodePASS|[types](evidence/frontend-typecheck-current.log),[unit](evidence/frontend-unit-current.log)|
|Current Playwright Auth+session,workers1,mockVite5188|25PASS|[log](evidence/frontend-auth-current.log);newcooldown RED first;artifact root riêng|
|HTTPAuth TCP reuse/burst/cancel|1PASS|[log](evidence/auth-tcp-pool.log);20warm samples,cold32ms/warm p9532ms,80burst requests,peak20≤configured64;0open sockets after close;noTLS|
|Linuxdeploy unittest,Docker-capableimage/networknone|37PASS|[log](evidence/deploy-linux-with-docker.log)|
|Linux realUvicorn SIGUSR1/SIGTERM|LOCAL_SYNTHETIC_PASS|[log](evidence/linux-signal-smoke-3.log);cleanup0.215s,exit-15 is Uvicorn signal re-raise,cleanup marker confirmed;noactiveAI/DB|

Final backend command from `backend`,owned disposable marker+TEST_DATABASE_URL,`AI_DISPATCH_GATE_ENABLED=true`:
`python -m pytest tests/test_sdk_adapter.py tests/test_orchestration_sdk.py tests/test_orchestration_sse.py tests/test_groups_turn.py tests/test_collaboration_chat.py tests/test_collaboration_privacy.py tests/test_journal_auto_memory.py tests/test_budget_reservations.py tests/test_guest_global_budget.py tests/test_scale_review_fixes.py tests/test_auth_flows.py tests/test_auth_captcha.py tests/test_scale_auth_reliability.py tests/test_scale_polling.py tests/test_scale_drain.py tests/test_ai_capacity_config.py tests/test_scale_readiness_safety.py -q`.

All destructive DB work uses exact UUID/loopback/container ownership checks;no hosted tests.
Earlier omitted marker caused setup refusal,not a DB reset;corrected rerun passed. A runtime-state
regression attempt was interrupted while output was buffered;the unbuffered190-test rerun above completed.
Wrong test filenames caused collection-only errors and are retained;they are not counted as PASS.
First signal-smoke mistakes used conversation-create instead of message route and assumed exit0;
corrected smoke checked actual drain route and completed lifespan cleanup before signal re-raise.

Auth CAPTCHA/origin/bruteforce/email cooldown/confirmation retained;session,consent,ownership and
financial locking remain authority.New metrics omit private payloads.The previous DB credential
exposure in `backend/runtime.txt` is still a **production security blocker**;not rotated or printed.
Crash/cancel/late/unknown regressions passed within their scope;no full50-user chaos/restart/network proof.
Fresh review fixed3Important findings;subsequent fixes have their own RED/GREEN evidence;
[review record](evidence/final-code-review.md). No second independent review claimed.

Scoped lint/mypy,diff/docs checker and cleanup results are in [delivery verification](evidence/delivery-verification.json).
Docs checker has pre-existing missing links from user-deleted old documents;no restoration of unrelated files.

## F. Owner approvals

C02a identity+verification is **APPROVED/EXECUTED/VERIFIED**. Remaining exact proposals,
benefit/security/cost/downtime/prerequisites/verification/rollback are in [14](14-owner-decisions-required.md):

|Change|Recommendation/benefit|Risk,cost,downtime|Rollback/approval|
|---|---|---|---|
|C01 DBcredential rotation|Coordinated consumer/vault transition to revoke exposed credential|DB outage if consumer missed;scope/window unknown;cost not quoted|Reviewed transition;do not restore compromised secret.Individual approval pending exact scope|
|C02 productiondomain/SES/SMTP/quota|Owner-controlled domain,DNSalignment,reviewed sender/rates before100real signup|Email outage/abuse/usage charges;price unknown;Gmailcanary does not close gate|Previous verifiedSMTP/config from vault;do not clear suppression.NOT_READY;domain later|
|C03 reviewedimage + NATpolicy|150/action/60s,600IP/900s,CAPTCHA/email/bruteforce retained|Abuse/provider traffic,image recreate downtime;no new fixed service|Flagfalse→legacy40/900 and compatible image;no data rollback.Pending staging prerequisites|
|C04 global50 + bounded/dispatch|Versioned provable envelope and50-parent policy after money/quality/load proof|Context>64k rejected,preflight latency,unsupported search;all-provider scope open|Stop admission;retain all liabilities;review compatible legacy image.NOT_READY|
|C05 DB/resource/drain/deploy|Budget verified against effective role/pooler;rehearse before any resize/restart|SPOF/downtime/timeouts/resize charges;RPO/RTO unknown|Compatible digest/env,fence workers,retain ledger.NO resize/role change recommended solely from local failure|
|C06 observability/backup|Choose notification channel/retention,priced alarms and isolated restore|PII/monitoring/storage cost orbadrestore;no quote|Reviewed oldconfig/retention;never delete backups automatically.NOT_READY|

No blanket production approval requested. Safe local engineering does not require owner to repeat D03/D05/D10/D12.

## G. Release decision

|Gate|Status|Remaining evidence|
|---|---|---|
|G00 provenance|PARTIAL|Dirty-source hashes/local tools;no published immutable candidate|
|G01 cloudfacts|PARTIAL|Compute/pooler/SMTP/Auth/OpenAI quotas unknown|
|G02 security/recovery|BLOCKED|Exposedcredential notrotated;restore rehearsal absent|
|G03 1000accounts|PARTIAL|Synthetic only;confirmedAuth/growth absent|
|G04 distributedsignup|LOCAL_ADMISSION_ONLY|Actualdelivery/confirm/login cohort absent|
|G05 NATsignup|LOCAL_ADMISSION_ONLY|Hostedrate/egress/email policy absent|
|G06 DBbudget/performance|FAILED/PARTIAL|Calculator fixed;poolp95/soak not met|
|G07 financials|PARTIAL|Boundedrow tests;pooled/all-provider/campaignscope incomplete|
|G08 50AI/15min|FAILED|Peak50 does not pass sustained occupancy/resource/SLO|
|G09 realprovider|NOT_RUN|Quota/pricing/staging/campaign guard prerequisites|
|G10 mixedbackground|NOT_RUN_FULL|FullT6/T7/multi-agent workload absent|
|G11 recovery/privacy|PARTIAL|Regressions not fullprocess/network chaos|
|G12 resources|FAILED/UNKNOWN|L0pool/CPU issues;targetEC2 envelope not measured|
|G13 observability|PARTIAL|Some metrics;alarm/canary delivery not configured|
|G14 deployment|PARTIAL|37Linuxunit +signal smoke;active-turn/fencing/rollback rehearsal absent|
|G15 approvals/signoff|OPEN|Exact production changes not approved/ready|

**NO-GO** for the requested release. Implementation progress is not production verification.
No push/merge/deploy/hostedmigration/resize/IAM/DNS/SMTP/runtimebudget changes occurred.
Only approved external mutation:C02a oneSES canary identity plus verification.


## Continuation verification — 2026-11-05T15:33:45.423Z

### CI changes and evidence

- Baseline run [#362](https://github.com/mhiu05/MoodPrint/actions/runs/42028979060) failed with the reported 2,276 passed, 3 failed and 4 skipped. The three failures were in the collaboration defaults wrapper, multi-message cancellation timeout and web-search mock settings.
- Test-only fixes are on `feat/upgrade-user`: [d655ee86](https://github.com/mhiu05/MoodPrint/commit/d655ee86db041f258340a0f61528a9130b803d8d) explicitly passes `dispatch_enabled=False`; [48a1df2f](https://github.com/mhiu05/MoodPrint/commit/48a1df2f51817476ee5fda7bffe5924124c9f0ef) allows 10s for cancellation model startup under CI scheduling; [fdb5dc98](https://github.com/mhiu05/MoodPrint/commit/fdb5dc9897562b0d8550058218f7579411b1c2c5) supplies `ai_dispatch_gate_enabled=False` in the web-search fixture. These commits change tests only; they do not alter runtime product behavior.
- Run [#363](https://github.com/mhiu05/MoodPrint/actions/runs/42050805055) and [#364](https://github.com/mhiu05/MoodPrint/actions/runs/42051109147) completed with failure in “Backend checks against disposable PostgreSQL”; later workflow stages were skipped. They do not establish a pass.
- Run [#365](https://github.com/mhiu05/MoodPrint/actions/runs/42051313537), for the code-fix tip `fdb5dc9897562b0d8550058218f7579411b1c2c5`, was still in progress in that same backend-check step at capture time. Documentation-only runs #366–#368 were also in progress after their respective commits. Treat all of these as unverified until the latest applicable run completes.
- No local test suite was run in this workspace. GitHub Actions is the verification path. No merge to `main` or deployment occurred.

### Gate status after read-only cloud review

| Gate | Status | Current evidence / remaining blocker |
|---|---|---|
| G00 | PARTIAL | Test fixes pushed; CI is still running, no immutable deployed image/digest. |
| G01 | PARTIAL | EC2, Supabase and SES facts verified; OpenAI staging quotas and AWS billing/cost remain unknown. |
| G02 | BLOCKED | Exposed owner credential is active; no hosted DB/Storage/EBS restore rehearsal. |
| G03 | PARTIAL | Synthetic-account evidence only; no hosted 1,000-user confirmation/login proof. |
| G04 | LOCAL_ADMISSION_ONLY | No real 100-user distributed signup/delivery/confirmation cohort. |
| G05 | LOCAL_ADMISSION_ONLY | No real 100-user one-NAT delivery/confirmation cohort. |
| G06 | FAILED/PARTIAL | Pool/performance and mixed-load SLO evidence remains insufficient. |
| G07 | PARTIAL | Pooled, all-provider financial accounting and crash/retry proof remain incomplete. |
| G08 | FAILED | 50 concurrent turns for 900s have not passed the full profile/SLO. |
| G09 | NOT_RUN | Correct OpenAI staging project and safe real-provider adapter are not verified. |
| G10 | NOT_RUN_FULL | Full mixed interactive/background workload is absent. |
| G11 | PARTIAL | Full network disconnect/replay/revoke/restart/cancel chaos evidence is absent. |
| G12 | FAILED/UNKNOWN | Target EC2 sustained CPU/memory/OOM envelope was not measured; no numeric metric sample was captured. |
| G13 | PARTIAL | CloudWatch metrics exist, but no alarms, notification channel or recovery canary is configured. |
| G14 | PARTIAL | No active-turn drain/fencing/rollback rehearsal. |
| G15 | OPEN | P0/P1 blockers and final release approval remain open. |

Release remains **NO-GO**. These statuses are not upgraded by a code push, local mock, healthy idle EC2 instance or dashboard read.
# CI repair evidence — 2026-11-05

Original GitHub run [42028979060](https://github.com/mhiu05/MoodPrint/actions/runs/42028979060),
SHA `e4e56997d6088516de009eaeca9d5a89461e9eb5`: **3 failed,2276 passed,4 skipped**,
926.16s. All three failure names in the owner's report are confirmed in its log.
Linux3.12.13 uses PostgreSQL17.10/pgvector0.8.2 in a unique tmpfs container; every
direct pinned dependency and dev-tool version matches pyproject. No hosted DB or
provider secret is mounted. The original scoped RED has2 failed/1 passed: wrapper
missing dispatch parameter and incomplete settings double. Cancellation passes in
isolation (0.37s call) and in the original-order full Linux run; its CI-only3s timeout
has **not** been independently reproduced as a production scheduling defect.

Cancellation validation now covers dispatch false/true and waiting-slot/in-model
states. Readiness races model-start against the owned drive task, retaining the
unchanged runtime deadline and exposing early run failure; it does not enlarge a
test timeout. Terminal task completion, provider cancellation and durable no-bubble
state are asserted. No production scheduling fix is claimed without reproduction.

Intermediate GREEN:86 tests in the original three files; pooled/legacy21 tests;
expanded pooled/legacy/snapshot/revocation-lock32 tests; Ruff passed and mypy passed
195 source files. Expanded handoff assertions were corrected to account for the
existing proof's initial turn and direct-specialist continuation, retaining every
original SDK/privacy assertion. Error-boundary/guest-deadline failures were traced
to inherited STATIC_DIR in the test image, then3 tests passed with aligned runner
environment and the real SQL-review path fix. The latter prohibits repo artifact
writes even when the checkout itself is under OS temp.

The new900s T4 attempt failed at257.592s wall/197.592s measurement:462 attempts,
461 completed,mean occupancy41.43/50,peak50 parents/SSE/provider calls,one pool
timeout,one noncompleted stream; pool recent-window p95=735.958ms,loop p95=29.93ms,
peak RSS199929856bytes. Financial invariant held; peak liability7820400000nano.
This diagnostic overlapped the original-order suite and is not an isolated target
benchmark. SQL-structure reuse is under regression/remeasurement; pool4+1 and all
timeouts are unchanged. **P3-I07 remains FAILED; P4-E01 target load remains absent.**

Artifacts: [scoped RED](evidence/ci-repair-scoped-red.log),
[pooled RED](evidence/ci-repair-pooled-red.log),
[financial/security GREEN](evidence/ci-repair-accounting-security-green.log),
[additional GREEN](evidence/ci-repair-new-green.log),
[T4 failure](evidence/ci-repair-T4-before.json),
[AWS facts](evidence/ci-repair-aws-readonly.json),
[SES/EBS/SSM](evidence/ci-repair-aws-additional.json).
Zero paid generation/judge calls,zero external generation spend,no deployment or
production-budget activation. New remote CI/SHA evidence will be appended after push.

Pre-push verification: **124 passed** in108.70s across the three original files,
pooled accounting, legacy budget, fresh snapshot, live revocation/lock races and
guest SQL-review tests. Another **21 passed** in22.24s covers both SQL-review
generators and session-reliability errors with STATIC_DIR removed. Ruff passed;
mypy passed195 source files. These scoped counts overlap and must not be added
as a distinct full-suite total. Independent read-only code review found no blocker
in pooled transfer/recovery, immutable SQL-structure reuse, cancellation lifecycle
or resolved-path artifact guards.

The original-source full diagnostic (before fixes, with image STATIC_DIR and no
Git metadata) finished **13 failed,2266 passed,4 skipped** in1782.94s. All13 are
accounted for:2 known contract failures,7 SPA-shadowed dynamic test routes,
2 missing-Git reviewed-artifact checks,and2 genuine SQL-export path guards in a
checkout under/tmp. The original cancellation test passed in this order. This
diagnostic is not reported as an equivalent full CI run; the new GitHub workflow
is the authority for the final source and exact counts.

Controlled cancellation RED/GREEN: the same real runtime/DB/model test was driven
with its runtime slot held for3.25s (within the unchanged runtime deadline). The
original3s startup wait failed with TimeoutError (1 failed in11.98s); lifecycle
readiness passed on the same scenario (1 passed in9.86s), including terminal task,
provider cancellation and no committed bubble assertions. This is a controlled
backpressure reproduction, not evidence of a production deadlock or a reproduced
natural CI schedule. Logs: [RED](evidence/ci-repair-cancel-backpressure-red.log),
[GREEN](evidence/ci-repair-cancel-backpressure-green.log).

The isolated follow-up at source `bab7bad140be46e9ab9f98322fa0174354a3ef8f`
completed the full900.0s measured window (978.193s wall): **1953/1953 completed,
zero errors,zero pool timeouts**,peak50 parents/SSE/provider and199184384bytes RSS.
Liability peaked16027950000nano,within the50USD test cap. It still **FAILED**:
mean occupancy43.69<45,and recent-window pool p95=748.517ms>100ms. Completion
p95=28757.929ms,p99=30614.367ms;loop p95=24.289ms. LocalDocker has12CPUs and
8171651072bytes;this does not establish the target2-vCPU EC2 envelope.
[Full report](evidence/ci-repair-T4-after.json);source SHA256
`1cb00c7effa4f626b94d4bddcc4d190ebb913c9f72ae18e8f928334687633506`.

Rejected pressure experiment: registered running saved polls without receipt/step
projection,recovery or configured transaction timeouts used one fresh joined
authorization/run snapshot. RED was3 SQL vs required1; **59 tests passed** over
fresh provider/session revocation,expiry,auth version,age,suspension,deletion,AI
row,data version,conversation expiry,saved chat and guest lifecycle. Guest/terminal/
receipt/transaction-timeout routes retain their existing validation. No policy or
result cache;unchanged pool/timeout. Independent review found no blocker. Ruff
passed and mypy passed196 source files. Its subsequent load failed; this implementation
and the follow-on coalescing reader are absent from the delivered source.
Logs: [poll RED](evidence/ci-repair-poll-red.log),
[authorization regressions](evidence/ci-repair-poll-security-green.log).

Full GitHub workflow [42115340645](https://github.com/mhiu05/MoodPrint/actions/runs/42115340645)
completed **SUCCESS** at source `bab7bad140be46e9ab9f98322fa0174354a3ef8f`:
backend **2300 passed,4 skipped,0 failed** in1118.76s;Vitest206 tests/37 files;
Playwright E2E388;full-stack38;AWS release poller37. Ruff,mypy195 files,migrations,
synthetic load,contract drift,docs,12 SQL approvals,workflow syntax and all Docker
packaging/build steps passed. These are separate suites,not an aggregate total.
[Exact summary](evidence/ci-repair-ci-bab7.json). The next commit retains this runtime
and adds authority/runner regressions plus evidence; its exact-SHA workflow must
finish independently before it is described as verified.

The one-snapshot attempt measured900s but completed1932/1933,with one pool timeout,
mean occupancy43.12 and recent poolp951054.135ms: **FAILED**.
[Report](evidence/ci-repair-T4-snapshot.json),source SHA256
`d56f946a5f64729af1db7281c51106a1bd7149592fd9a4f183b9db898102d401`.
Coalescing fresh reads reduced14905 logical polls to1495 SQL batches,but stopped
at291.071s wall/231.071s measurement:546/561 completed,15 pool timeouts,poolp955500.72ms,
mean occupancy40.17,completionp9533320.481ms: **FAILED**.
[Report](evidence/ci-repair-T4-batched.json),source SHA256
`a60420bc576313a6faeb0464fbb2325140f1f8a1580e78d18e2cc7a65b0e6398`.
Isolated EXPLAIN ANALYZE was8.923ms/50 rows;10 batches took0.250s. This does not
explain all workload pressure or establish a database lock regression. No pool,
deadline or target threshold was raised. Both experiments were removed because
the measurements did not support shipping them;original tests remain intact.

Retained continuation:10 additional live authority-change regressions,including
provider/application session,expiry,auth version,age,suspension,deletion,purpose,
data version and conversation expiry. Sequential scope **82 passed in214.80s**
includes saved chat,session reliability,guest lifecycle and the first runner checks;
it is not a new full-suite total. An earlier overlapping fixture-reset run is invalid
and was discarded;only sequential DB-suite evidence is used.
[Scoped log](evidence/ci-repair-final-scoped-green.log).

Runner defect fixed: parent peak/occupancy alone no longer produces a local PASS.
It also requires all admitted turns complete,no rejection/error,financial invariant,
full measurement window,single completionp95≤30s/p99≤60s,recent poolp95<100ms with
zero timeouts,and event-loop lagp95<100ms. Monitor exceptions/early exits fail closed;
errors contain only task names and exception types. Gate decisions use raw numbers,
so rounding cannot convert44.999 occupancy or899.9996s into a pass. The JSON retains
explicit unmeasured release gates;recent2048 pool samples never claim a whole-run
distribution. The CI Ruff command now includes this script.
RED13 failures,then review RED4 failures;final **28 passed in0.37s**.
Logs:[initial RED](evidence/ci-repair-runner-slo-red.log),
[review RED](evidence/ci-repair-runner-review-red.log),
[GREEN](evidence/ci-repair-runner-slo-green.log). Ruff passed,mypy195 files passed
after removing the experiments. All generation/judge/email calls remain synthetic
or absent,external generation spend remains zero. P3-I07/P4-E01 remain FAILED.

Final runner integration smoke (30s,no warmup;**not** a900s acceptance run):70/70
completed,zero errors/timeouts,peak50,measurement tasks healthy. The report correctly
returns **FAILED** for occupancy42.659,completionp9531507.274ms,and recent poolp95659.845ms.
It exposes each failed local gate and the unmeasured release gates explicitly.
[Report](evidence/ci-repair-runner-final.json),source SHA256
`dcd57bf1c903da4d9c5b9345b6806ee66ad7f45c0bf2e4ceb33f85d2fd8e5708`.

Final Linux scoped verification: **162 passed in164.86s** across the three original
failure files,pooled/legacy accounting,live polling authority,runner safety and SQL
review guards. [Log](evidence/ci-repair-final-regressions-green.log). Ruff passed
including scale_readiness.py;mypy passed195 files;docs208 Markdown/1446 links and
12 reviewed SQL approvals passed. Independent review found no remaining concrete
blocker after both runner findings were fixed. These tests overlap prior scopes;
the post-push full GitHub workflow,matched to the exact remote SHA,is the final
suite authority. No merge or deployment follows a green feature-branch workflow.

## Codex engineering continuation — 2026-11-06

**Current retained-source decision: P3-I07 FAILED; all runtime experiments below were rejected and removed. Only stronger pool measurements/SLO gates and additional regressions are retained.**

Measured baseline profiling found substantial repeated SQL/client work:37,965 instrumented
SQL events; periodic policy monitors alone held connections for128.251aggregate seconds
over2,453checkouts (mean52.283ms,p95102.802ms). Instrumentation overhead invalidates this
as an acceptance comparison. [Content-free profile](evidence/p3-baseline-profile.json),
[profile workload](evidence/p3-baseline-profile-workload.json).

Focused REDs: monitor resource contract5SQL versus the reduced target, running SSE3SQL
versus1, missing poolp99/whole-run gates (3failures), and a delayed-checkout expiry test
that failed DID NOT RAISE DomainError. Final focused scope **113passed in69.26s** includes
polling/authority, persistence/replay, cancellation/drain, legacy/pooled accounting,
resource guards and runner safety. These counts overlap prior scopes and are not a
full-suite aggregate. [SSE RED](evidence/p3-stream-red.log),
[expiry RED](evidence/p3-monitor-expiry-red.log),
[pool RED](evidence/p3-pool-metrics-red.log),
[GREEN](evidence/p3-combined-green.log).
Exact Linux CI Ruff scope passed; full `mypy app` passed197 files. Independent reviews
found no remaining Critical/Important issue after the expiry fix and test hardening.

Corrected isolated short baseline (60s measurement/15s warmup):161/161 completed,
0errors/timeouts, mean occupancy44.8643, pool recentp95368.248ms, completionp9529546.205ms:
**FAILED**. [Report](evidence/p3-baseline-v2.json).

Combined short diagnostic:207/207 completed,0errors/timeouts, occupancy45.7506,
completionp9524287.809ms, looplagp9511.327ms, final pool windowp9538.465ms/p9997.930ms.
It overlapped the end of cold typing and is **not a comparable acceptance run**.
Its whole-run pool thresholds failed, and the strengthened runner correctly returned
**FAILED** despite the healthy final window. [Report](evidence/p3-combined-short.json).

Measurement scope: `whole_run` means pool lifetime through collection, including fixture
setup/warmup/drain. Its counters exactly decide nearest-rank p95<100ms/p99<500ms; they
do not invent lifetime percentile values. `_do_get` times queue/create work and excludes
pre-ping/SQL. Occupancy excludes warmup/drain. No report here proves network/EC2 capacity,
the full mixed workload, real-provider pricing/quota/quality or all-provider accounting.

An interrupted900s attempt has no final workload result; its676 resource samples end
at682.352s. A separate0.5GiB disposable-DB cap caused confirmed fixture OOM during resets;
that44PASS/33setup-error run is invalid for implementation comparison. Both limitations
are retained in [qualifications](evidence/p3-experiment-qualifications.json) and
[interruption record](evidence/p3-monitor-soak900-interrupted.json).

The completed replacement was isolated from other local test/typecheck workloads and
persisted artifacts directly to the workspace. Its failed decision is recorded below;
P3-I07 is not promoted. Baseline source07486b83 CI attempt2 was re-read as completedSUCCESS;
the new feature push must obtain its own exact-SHA completed workflow. No merge/deploy
follows a successful feature workflow. External generation/judge spend remains0.

### Full-soak finding and transaction follow-up

The first completed isolated900s candidate **FAILED**:2441/2441 completed,0errors and
0pool timeouts, occupancy46.08085/50, completionp9523829.625ms/p9925526.455ms, but pool
recentp95838.175ms/p991431.516ms and both exact lifetime thresholds failed. Lifetime
counts:213874 acquisitions,132214 below100ms,199484 below500ms. Peak parents/SSE/provider
were50/50/50; RSS200552448bytes; simulated ledger liability18423660000nano. Process
CPU950.655s over982.418s wall shows a nearly saturated single application CPU despite
its2CPU quota. The database quota was not throttled. This is not a P3-I07 PASS, and the
SSE/monitor-only variant does not qualify for shipping as a completed contention fix.
[Full report](evidence/p3-combined-soak900.json),
[resource samples](evidence/p3-combined-soak900-resources.json).

Native sequential cold EXPLAIN timings are recorded separately; they are not workload
latencies. A physical-driver control-command probe identified avoidable transaction
traffic:20 single-statement reads sent20BEGIN+20ROLLBACK; autocommit reads sent neither.
[Sanitized plans](evidence/p3-explain.json), [wire-command probe](evidence/p3-protocol.json).

The follow-up confines autocommit to the two read-only snapshot helpers. A cached derived
engine shares the existing pool and restores isolation before reuse; fresh AsyncSessions
and all writer/provider/publication/recovery transactions are retained. Pre-ping, pool
limits, model/context, polling intervals and deadlines are unchanged. No global rollback
reset is disabled. This uses the documented [SQLAlchemy shared-pool isolation pattern](https://docs.sqlalchemy.org/en/20/core/connections.html#maintaining-multiple-isolation-levels-for-a-single-engine).

RED:missing snapshot reader. GREEN:114 focusedPASS; then2 focused normal/cancelled-reader
reuse cases PASS, including cancellation of an active PostgreSQL query and a subsequent
writer UPDATE that must roll back. Counts overlap. Ruff passed and full mypy197 files
passed before the next isolated900s run started. Independent review found no
Critical/Important issue. [Cancellation/reuse verification](evidence/p3-autocommit-cancel-green.log).
Historical checkpoint: that follow-up was pending here. Its failed outcome and rejection are recorded below; none of that runtime variant is retained.


### Rejection and retained-source decision

The autocommit replacement failed its first cohort:42/50 completed,8pool timeouts,
4DATABASE_BUSY and4unfinished streams; completionp9550529.996ms. It stopped before
warmup completed (0s acceptance window). No OOM or CPU-quota throttle explains it;
the isolated micro-probe and114unitPASS/2cancel-reusePASS did not predict the actual
workload. The concurrency failure was not resolved, and the experiment was removed.
[Report](evidence/p3-autocommit-soak900.json),
[resources](evidence/p3-autocommit-soak900-resources.json).

The SSE/monitor-only variant also did not satisfy the pool SLO and is absent from the
retained source. Original3/5query-budget contracts and all original tests remain;
experiment-only contracts/APIs were removed with their implementations. Historical
RED/GREEN results above describe discarded candidates, not the delivered runtime.
Retained112tests PASS; exact CI Ruff PASS and mypy195files PASS. The retained-source900s request subsequently failed; its actual result is recorded below and is not inferred from these variants.

Measured topology limitation: nearly one full application CPU with no2CPU-quota
throttling, modest RSS, frequent client/idle-in-transaction waits and sampled admission
lock queues. This supports further application/read/dispatch architecture work, not a
larger pool/deadline or a claimed EC2 capacity ceiling. Financial and mixed/network
gates remain open. All external generation/judge spend remains0.

### Exact retained-source benchmark and delivery status


The exact retained-source900s request stopped on workload failure:209/217 completed,
8pool timeouts (6exception outcomes and2unfinished streams),126.9585s measured window,
187.047s workload wall, occupancy34.6617, completionp9548846.222ms/p9953987.336ms,
recent poolp954998.483ms/p998254.595ms. Process CPU183.023s/187.047s wall again approaches
one saturated application CPU without quota throttling/OOM. This is **FAILED**, not a
completed900s soak. The existing fail-closed runner was not weakened to continue past
errors or manufacture success. [Exact report](evidence/p3-retained-soak900.json),
[resource samples](evidence/p3-retained-soak900-resources.json),
[delivery summary](evidence/p3-retained-summary.json).

No experimental performance variant is retained. All original authorization/privacy/
cancellation/runtime code and original3/5query-budget tests remain. Retained112focused
tests passed in148.39s; Ruff and mypy195files passed. Full bare backend pytest is running;
the exact feature-push CI must complete before its conclusion is reported. A green CI
does not turn these failed performance, financial or mixed-workload gates into PASS.


Local full bare pytest interruption: the Docker daemon became unavailable again;
the persisted log ends near18% with no completion/exit artifact. This run is
**INTERRUPTED**, not a full regression PASS. The retained112focusedPASS, lint and
typing results remain their stated scopes. Exact feature-commit GitHub CI is the
full regression authority and must complete independently.
