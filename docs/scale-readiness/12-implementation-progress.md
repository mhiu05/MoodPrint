# Implementation ledger — plan: 08-implementation-roadmap.md

## Current execution override — owner update, 2026-11-05

**NO-GO; original41 IDs retained:2 DONE,27 IN_PROGRESS,7 BLOCKED,2 FAILED,3 DEFERRED.**
Current authority supersedes historical no-push/domain/RPO wording below:
commit and normal push to `feat/upgrade-user` authorized; no merge/deploy.
App URL remains DuckDNS; no domain/service purchase. Technical backup policy chosen
by Codex:RPO24h/RTO8h planning targets, not hosted recovery achieved. Named EC2 Start
authorized conditionally, but target is already **running m7i-flex.large**; no Start
was issued. All other consequential cloud changes still require specific approval.

New local engineering this round:

- Saved running poll4→3 SQL queries, preserving a fresh provider-session result on
  every read. Writers retain the separate provider check after the account lock.
  Review caught a pre-lock snapshot race; concurrent test reproduced RED then GREEN.
- Global financial liability5→1 SQL statement/snapshot; registered, detached guest,
  external search, unknown-history and halted-day safeguards retained. No cache,
  pool-size increase, timeout increase or rejected HTTP admission queue added.
- Bounded transport rejects remote item_reference input before count/generation;
  two tests reproduced the contract gap before the fix. Flags remain disabled.
- New durable campaign primitive:permanent reservations, multiprocess cap/crash
  tests. **Live adapter/application pooled accounting/all-provider coverage remain
  incomplete**; no real generation/judge calls or production$50 activation.
- Recovery verifier and isolated synthetic pg_dump/pg_restore with RLS/uncertain
  liability/object/config/secret-byte checks; failure cleanup now verifies immutable
  container ownership even after a launch timeout. No hosted backup enabled.
- Active exposed credential classified as **postgres migration owner**, distinct
  from runtime role; safe TLS read-only authentication succeeded. Exact rotation
  consumers/order/verification/recovery documented in20; no rotation executed.
- EC2 status/AMI/EBS/EIP/SSM diagnostic, effective numeric config and public DNS/TLS
  verified. Idle health is not target-size capacity or real-traffic proof.

Actual regression/load results:[15](15-test-results.md). Current cloud facts:[13](13-cloud-inventory-redacted.md).
Exact remaining actions:[16](16-work-handoff.md), paste-ready prompt:[17](17-work-execution-prompt.md).
Recovery:[18](18-recovery-runbook.md), campaign:[19](19-paid-campaign-runbook.md), security:[20](20-security-cloud-actions.md).

Ruling: use the existing41-task ledger and owner-designated files; no worktree/helper
that changes.gitignore. Original task status covers full acceptance, so new code
alone does not turn cloud/load/real-provider tasks intoDONE. Cost of a wrong status
would be false release readiness; preserve explicit NO-GO and scoped evidence.

Ruling: backup policy selection is now delegated; paid activation/hosted restore
is not. Prior statements that owner must choose RPO/RTO/domain before coding are
historical. Shared source is pushed GitHub, not Work's separate browser filesystem.

## Earlier implementation history (superseded facts explicitly noted above)

Ngày bắt đầu: 2026-11-05 (Asia/Bangkok). Branch `feat/upgrade-user`, baseline
`0573af5b50c0584c523e5119755479fcf47fae74`. Implementation local được owner cho phép;
prior round did not commit/push/merge/deploy or edit `.gitignore`/`.env`.

## Quyết định áp dụng

- D03 APPROVED: ưu tiên 100 legitimate signup cùng NAT, giữ CAPTCHA/email/brute-force/origin/proxy protections; policy production mới cần approval riêng.
- D05 APPROVED: chất lượng hội thoại ưu tiên; bound mới có ảnh hưởng UX đặt sau feature flag, không cắt history âm thầm.
- D10 APPROVED: read-only cloud và local engineering tự thực hiện; mỗi production mutation cần approval cụ thể. RPO/RTO vẫn cần chốt riêng.
- D12 APPROVED: toàn campaign tối đa $3, chỉ `gpt-6-luna` generation; coding agent đánh giá offline, không judge API. Chưa gọi paid API.
- Global application AI target $50/day; production activation cần approval. Guest allocation giữ nguyên.

Ruling: request mới thay thế các đoạn audit-only, $20 và $5 trong plan cũ. Giữ baseline lịch sử trong 01; các tài liệu hiện hành sẽ được đồng bộ. Sai sót có thể gây false readiness nên mọi kết quả gắn environment và scope.

Ruling: dùng ledger/evidence tại đường dẫn owner chỉ định, không tạo worktree, không chạy helper có thể thay `.gitignore`, không xóa evidence. Task chỉ DONE khi đủ acceptance; phần code đã xong nhưng cloud/load còn thiếu vẫn IN_PROGRESS/BLOCKED.

## Pre-flight interfaces

| Producer → consumer | Interface / ruling |
|---|---|
| P0-H01 → P1/P2/P4 | Actual staging t3.small, SES sandbox; t3.large là target, không phải resource đã xác minh. Không resize tự động. |
| P1-A02/A05 → P1-A10/P5 | Action policy candidate phải opt-in và có Retry-After; test mocks không chứng minh deliverability. |
| P2-D02 → P4/P5 | All-process overlap phải cộng API/proactive/maps cùng operational reserve; không dùng role20 như cloud fact. |
| P3-I02 → I03/I07/P5 | $50 không đủ 50 legacy $2 holds; giữ fallback và chỉ giảm reservation khi pre-dispatch bound được cưỡng chế. |
| P3-I09 → T5 | Public model documentation không chứng minh project access/RPM/TPM; thiếu quota/pricing/control thì zero paid dispatch. |

## Tiến độ

41 task được theo dõi ở bảng dưới; status áp dụng cho toàn bộ acceptance criteria.
Baseline workspace inventory was retained locally as `evidence/workspace-baseline.json`
(paths/status/hashes only); it is intentionally not published. The sanitized delivery
scope is in [round2 staging manifest](evidence/round2-staging-manifest.json).

## Evidence đang có (không phải production PASS)

- Auth RED→GREEN:429 Retry-After, timeout signup/resend/recovery không replay, lifespan-owned HTTP pool không chia sẻ bearer/cookies, candidate NAT150/action/60s +aggregate600/900s, giữ email3/h và login10/900s. Policy mặc định tắt.
- Frontend Playwright RED: hai submit cùng scheduler tick tạo2 calls. GREEN: khóa `useRef` tạo1 call; CAPTCHA regression PASS. Test artifact marker ban đầu đã được khôi phục byte-for-byte theo SHA256 baseline; các lần sau dùng artifact root riêng.
- Regression PostgreSQL:101 PASS ([log](evidence/backend-regression.log)); bounded financial/guest/retention:37 PASS ([log](evidence/bounded-accounting.log)); SDK/transport/safety:39 PASS. Full-suite historical result and rechecks are recorded in15.
- Polling RED:9 queries cho một running saved poll. GREEN: joined owner/turn/conversation và không query answers khi đang running; vẫn kiểm session/provider/eligibility/AI consent/data-version mỗi tick.48 regression PASS ([log](evidence/polling-regression.log)).
- Retention RED:old uncertain child bị xóa qua parent cascade. GREEN:giữ open/uncertain bất kể tuổi và xóa child an toàn trước parent. Không schema mutation.
- T1:1000 synthetic app users,1000 sessions,4000 consent; không confirmed Auth/growth90 ngày. T2/T3:100/100 accepted/60s, provider fake, không gửi thư.
- T4 legacy:$50 giữ được25 parent/SSE/provider,25/50 từ chối, liability50e9; dừng trước soak. T4 bounded burst:50/50 complete, peak50 parent/50 ASGI SSE/48 fake provider, hold6USD; không live-provider proof.

Ruling: thêm candidate envelope64k/1200/3 calls với hold$0.12, exact-count endpoint trước từng generation trên payload thật. Flag mặc định false; overlong input bị từ chối chứ không cắt history. Hosted tools/stateful/file inputs fail closed. Cần kiểm endpoint/pricing/account và owner duyệt UX trước production. Nếu contract khác kỳ vọng, candidate phải tiếp tục đóng; legacy$2 vẫn giữ.

Ruling: guest giữ full-context legacy reservation và quota/budget riêng; context-local dispatch marker bỏ qua preflight64k cho guest để lifetime guard không bị đẩy ra trước một network await mới. Queue nằm trước guard; không thay allocation guest.

Ruling: fixture load cũ không trả usage nên mỗi completion vẫn giữ uncertain liability. Đã tạo fixture riêng có usage mô phỏng8000/600; không sửa fixture lỗi để biến unknown thành free. Các report cũ được giữ nguyên. Input/output mô phỏng không phải tokenizer/quality proof.

Ruling: giữ tên metric `ai_sdk_first_delta_ms` vì nó bao gồm SDK/preflight; không gọi là provider/network TTFT. Chưa đủ metric để đóng observability gate.

## Task ledger — 41 original task IDs

Status applies to the FULL original acceptance criteria,not only code written. No task markedDONE solely on compilation.

| Task | Priority | Status | Owner | Files/evidence | Tests/actual result | Acceptance coverage | Remaining risk | Next action |
|---|---|---|---|---|---|---|---|---|
| P0-H01 | P0 | IN_PROGRESS | CODEX | 13; cloud JSON | AWS/Supabase/model GET | Facts ??ng target/source/time; compute/Auth/RPM/TPM c?n UNKNOWN | Hosted config/quotas incomplete | Read remaining dashboards |
| P0-H02 | P0 | BLOCKED | OWNER | 14 C01/C05 | No restore/rotation executed | Credential rotation+DB/Storage/EBS recovery rehearsal | Credential exposure security blocker | Approve exact scope/restore prerequisites |
| P0-H03 | P0 | BLOCKED | OWNER | 13;14 C02/C06 | SES/alarms inventory;C02a approved | Gmail canary identity verified;SMTP/CAPTCHA/quota/alarm prerequisites still open | SES sandbox;SMTP/rates/alarms UNKNOWN | Read SES/SMTP/identity/alarm facts; no domain prerequisite for coding |
| P1-A01 | P0 | IN_PROGRESS | CODEX | 13;SSM/public Auth | Read-only facts | Effective container/proxy/Auth/SMTP frozen | SSM is not effective deployed config | Complete hosted baseline |
| P1-A02 | P1 | IN_PROGRESS | CODEX | auth/admission.py;routes.py;config.py | test_scale_auth_reliability;T3-local | 100 NAT accepted plus negative abuse;production policy approval | Local100/100;CAPTCHA fake;hosted quota open | Staging real confirmation/login cohort |
| P1-A03 | P1 | IN_PROGRESS | CODEX | auth/routes.py;13 | Untrusted XFF/Sb header test | Full trusted proxy?BFF?provider IP behavior verified | Publishable egress mode preserved;forwarding not activated | Inspect effective Caddy/Uvicorn/hosted forwarding |
| P1-A04 | P2 | DONE | CODEX | auth/provider.py;main.py;auth-tcp-pool.log | Client lifecycle/cookie tests;TCP loopback benchmark | Reuse,finite pool,80-request burst/cancel,zero sockets after close;20 warm samples | TLS/cloud reuse latency not measured;local peak20 vs configured max64 | Keep pooling;validate TLS in approved canary |
| P1-A05 | P1 | DONE | CODEX | auth/provider.py;core/limits.py;Auth.tsx | mail-errors RED→GREEN;25 current Playwright PASS | Retry-After bounded,UI cooldown/manual retry,no false sent on unknown4xx;identity errors opaque | Hosted mail/provider behavior still unverified | Complete hosted baseline and controlled canary |
| P1-A06 | P1 | IN_PROGRESS | CODEX | auth/provider.py;auth/routes.py;Auth.tsx | reset-fence 3 RED→70 PASS regression | Local revocation commits before remote password change;DB failure means0PUT;lost response remains fenced/nonretryable | Rejected/unknown reset can log out old local sessions;no distributed exactly-once promise | Review UX;complete ambiguous signup/CAPTCHA matrix |
| P1-A07 | P1 | IN_PROGRESS | CODEX | test_auth_flows.py;provision-faults.log | 100 first logins+duplicate identity;3 fault cases PASS | Flush/commit/view failure emits no cookie;retry yields1User/4Consent;view-failure unissued session retained | Full provisioning latency/lock distribution not measured | Benchmark session/first-login;retain safe orphan policy |
| P1-A08 | P0 | BLOCKED | OWNER | 13;14 C02/C02a;ses-canary-identity.json | Owner-approved Gmail identity verified SUCCESS | Canary sender verified;verified-email authorization/DMARC/SMTP/quota still open | Sandbox200/day1/s;Gmail is canary only | Inspect Gmail alignment and quotas;exact SMTP/domain proposal only if needed |
| P1-A09 | P1 | BLOCKED | OWNER+CODEX | 13;14 C02/C06 | No SES events dispatched | Dedup/out-of-order events+delivery/confirm timeline | No configuration set/emailcanary | Prepare event fixtures after sink/channel chosen |
| P1-A10 | P1 | IN_PROGRESS | CODEX | T2/T3-local;Auth tests | 100distributed and100NAT/60s;24 E2E | Auth negative scenarios plus real email/confirmation+mixed | Acceptance only;not actual mail account capacity | Close A05/A06 then approved hosted cohort |
| P1-A11 | P2 | DEFERRED | OWNER+CODEX | 03 optional alternative | Not implemented | Only consider if provider quotas cannot support burst | No evidence queue/service needed | Prefer existing stack;revisit after quota facts |
| P2-D01 | P0 | IN_PROGRESS | CODEX | 13;supabase-catalog.json | Read-only catalog/MCP | role20/server60/regionPro verified;poolerSKU/servicepeaks required | Unknown pooler/backend budget | Read compute/pooler configuration |
| P2-D02 | P1 | IN_PROGRESS | CODEX | database/budget.py;runtime.env.example | test_ai_capacity_config;session/proactive budgettests | steady8/overlap16+reserve4,cap10/replica rejects | Calculator fixed;deploy prelaunch effective-override rejection missing | Wire deployment gate against actual role/pooler facts |
| P2-D03 | P1 | IN_PROGRESS | CODEX | ai/chat_routes.py;database/connection.py;security.py | Poll9→6→4;190 default regression;242 final candidate | Fresh privacy checks preserved;pool/15min gate not met | Windows19timeouts,Linux900s1timeout;later60s0timeouts but p95>1s | Use profiling for next SQL/CPU work;no pool increase without hosted facts |
| P2-D04 | P1 | IN_PROGRESS | CODEX | core/security.py;errors.py;config.py | Held-row SQLSTATE55P03;503mapping | SET LOCAL before rowlock,no statebleed;all paths/cancel faults | Opt-in registered transaction helper;not every job/admission class | Measure/extend bounded waits without paid retries |
| P2-D05 | P1 | IN_PROGRESS | CODEX | test_auth_flows.py;T2/T3 | 100firstlogin passed | Distinct andduplicate provision/session p95/p99/pool benchmark | No full latency distribution for provisioning | Add endpointtiming dataset separate from signup |
| P2-D06 | P2 | IN_PROGRESS | CODEX | 13;performanceadvisor | Inbox rerun p95=26ms | 1000users90day/skew EXPLAIN before index changes | Lint11FK gaps not benchmark proof | Seed representative90day dataset;collect plans |
| P2-D07 | P2 | IN_PROGRESS | CODEX | jobs/retention.py;test_scale_retention_safety | uncertain parent/child retention RED?GREEN | Financial rows safe;bounded multi-table/session/storage retention | No sessionTTL approval;long transaction unchanged | Choose TTL and implement per-batch transaction budget |
| P2-D08 | P1 | IN_PROGRESS | CODEX | 13;sessionhelper catalog;ownership tests | 48history/recovery tests;Supabase securityadvisor | RLS/roleflags/helpergrants/cross-user behavior incl new queries | Full role/browser grants audit not completed | Finish catalog matrix and all cross-user paths |
| P2-D09 | P2 | DEFERRED | CODEX+OWNER | 04 canary proposal | Existing prepare_threshold=None retained | Transaction pooler only after measured benefit/compatibility | Actual endpoint mode/limits UNKNOWN | No topology change until baseline pressure understood |
| P2-D10 | P0 | BLOCKED | OWNER | 13;14 C05 | Read-only backup inventory | DB+Storage+secret restore andRPO/RTO measured | RPO24h/RTO8h chosen;synthetic restore only;hosted restore/RTT unmeasured | Read actual backups;approve exact isolated hosted restore/cost;policy already selected |
| P3-I01 | P1 | IN_PROGRESS | CODEX | core/capacity.py;local-capacity-config.json;SSM | test_ai_capacity_config | Allowlist/dedup lines/model/pricing/flags;effectivecontainer source | Localduplicates diagnosed;actualruntime snapshot missing | Expose/run explicit diagnostics in reviewed deployment |
| P3-I02 | P0 | IN_PROGRESS | CODEX | ai/envelope.py;accounting.py;guest_model.py | bounded-accounting37;HTTPenvelopetests | Everydispatch64k/1200/3calls,budget50;legacyholds retained | Workflow pooled allocation not implemented;allprovider scope/countpricing unknown | Keepflagfalse;finish moneyproof+quality/account checks |
| P3-I03 | P1 | IN_PROGRESS | CODEX | ai/dispatch.py;provider.py;persistence.py;proactive.py | 50parents+children gateunit;parentDBcounttest | Finite cancellation-safe queue,API50/proactive2,parents distinct | Single-topology split52 is candidate;allprocess quotas notverified | Targetstaging fanout/lane-fairness/dispatchheaders |
| P3-I04 | P1 | IN_PROGRESS | CODEX | dispatch.py;connection.py;main.py;scale_readiness.py | Resourceguards;L0 reports | Separateparent/SSE/modelcalls/pool/loop/RSS,content-free | sdkfirstdelta includespreflight;no full stage/physicalHTTP timegraph | Add complete stage metrics and instrumentation checks |
| P3-I05 | P1 | IN_PROGRESS | CODEX | core/streams.py;runtime.py;chat_routes.py | 48history/recovery/events;globalstreamtest | Replay/cancel/privacy/leak cap100;slowreader/restart matrix | ASGI streams notTCP/TLS;finiteconnectionlifetime missing | NetworkSSEfault profile after poolpressure fix |
| P3-I06 | P1 | IN_PROGRESS | CODEX | dispatch.py;provider.py;14 C04 | Backgroundshare gateunit;guest tests | Boundedlanes/consent;allpaidoperations budget authority | RegisteredVoyage/STT accounting not integrated;Voyageclient reuse notdone | Resolve paid scope before claimhardglobal50 |
| P3-I07 | P1 | FAILED | CODEX | scale_readiness.py;scale_readiness_server.py;T4-bounded-soak-2 | 50peak/100attempts83complete/19pooltimeouts | 50active15min+mixed profile/SLO/resources | 900s target stopped at113.641swall;only53.641smeasure | Fix measuredDBpressure then rerun;no paidcalls |
| P3-I08 | P1 | IN_PROGRESS | CODEX | accounting.py;retention.py;faulttests | bounded37;101regression;recovery suites | Crash/unknown/late/cancel/midnight/guestliability safe | Full50fault/fanout/restartchaos matrix missing | Extend ownedprocess fault harness |
| P3-I09 | P0 | BLOCKED | OWNER+CODEX | provider-readonly.json;ai-cost-report.md | ModelGET200;zero generation | Actual RPM/TPM/prices/stagingidentity/campaign3controller | Quota/countfees/liveadapter unverified;durable campaign primitive25tests now exists | ReadLimits;bind canonical campaign ledger to reviewed exact-count one-wire adapter |
| P3-I10 | P2 | IN_PROGRESS | CODEX | core/outbound.py;provider.py | SDKadapter/envelope/shutdown tests | Boundedmodeltransport,retriespreserved,close lifecycle | No socketreuse baseline+Voyage pooling measurements | Measure transports at50 afterDBbottleneck |
| P3-I11 | P2 | IN_PROGRESS | CODEX | ai/chat_routes.py | Savedpoll3queries after4;freshprovidercheck;current regression24PASS | Lowerpollingquerypressure without staleauth/recovery | Current load retains checkout/CPU pressure;network notifications notimplemented | Profile shorttransactions and implement safe waking/batching |
| P3-I12 | P2 | DEFERRED | OWNER+CODEX | 05 optional topology | Not implemented | Only aftersingleprocessgates andnewsharedstate design | No evidence extraarchitecture needed | KeeponeAPIprocess |
| P4-E01 | P1 | FAILED | CODEX | T4reports;13 | L0RSS201.6MB;CPU/loop/pool stats | m7i-flex.large target-size50soak mixed/noOOM/pooltimeouts/FlexCPU economics | Hostverifiedrunningm7i-flex.large;targetload absent;localpoolSLO failed | Resolve measuredDBpressure;collect targetmetrics;no furtherresize |
| P4-E02 | P1 | IN_PROGRESS | CODEX | runtime.py;main.py;__main__.py;compose | test_scale_drain;Linuxdeploy37PASS | SIGUSR1drain503/newturnblock/readcancel;gracecoversgroup | No realSIGTERM/drain/workerfence/rollbackrehearsal | Wireapproveddeploysequence+rehearseisolatedLinux |
| P4-E03 | P1 | IN_PROGRESS | CODEX+OWNER | main.py;dispatch.py;connection.py;13 | Pool/streammetrics tests;AWSalarmread | Metrics+actualalarm/canarydelivery withoutPII | Noactualalarmchannel/configdelivery;stagemetrics incomplete | Finishmetricscontract thenreviewapplycost |
| P5-L01 | P1 | IN_PROGRESS | CODEX | scripts/scale_readiness.py;test_scale_readiness_safety.py | 10safety tests;T1T2T3T4 artifacts | CLI refusesunsafe/hosted/paid/overwrite;ownedcleanup;T1..T8full | T5/T7/T8blocked;T1growthpartial;ASGInotnetwork | Complete mixed/chaos/financialcampaign modes |
| P5-L02 | P1 | BLOCKED | OWNER+CODEX | 15-test-results.md;10gates | Current local evidence only | L0?targetstaging?approvedreal;exactprovenance/cost/cleanup | Criticalcloud/security/performance/qualitygaps | Keepreleasehold;completeengineeringbeforeactivation |

Rollback common:flagsfalse preserveslegacyAuth/reservations;revert reviewed code/image only after financial compatibility check,retainallopen/uncertain holds. No production runtime/schema mutation occurred;C02a SES canary identity was separately approved and verified. Test containers removed only by exactUUID/label ownership checks. Per-taskrollback details are in original taskcards and14;cannot undoalreadydispatchedcosts orpurgeddata.

Security impact:CAPTCHA/origin/session/consent/ownership/financiallocks preserved;newdefaultsclosed. Performance impact measuredonlyin reports;poolpressuregate FAILED despitequeryreduction. Costimpact:$0externalgeneration;no newpaidinfrastructure.

## Follow-up implementation and verification

- Fresh code review:3 Important findings, all fixed with5 RED tests then39 PASS;
  candidate-gate regression96 PASS/2 SKIP. [Review and rulings](evidence/final-code-review.md).
- Actor/session/age transaction-local prefetch:poll6→4queries,82 regression PASS.
  Runtime monitor joins state/conversation/accounting lease while keeping account/turn locks.
  Default-path Auth/history/guest/recovery/privacy regression:190 PASS in616.35s.
- Expanded candidate matrix found8 failures (136 PASS) in nested `Agent.as_tool()` calls:
  their nested Runner did not inherit post-queue hooks. Explicit wrapper fixed it;
  39 SDK/orchestration/queue-fence tests PASS. Full current candidate matrix is recorded in final-candidate-regression.log; see15 for actual result.
- Reset fault matrix:unavailable DB,commit failure,lost remote response:3 RED→70 PASS
  across Auth/CAPTCHA/reliability. Provisioning flush/commit/view faults:3 PASS.
- Frontend Retry-After:one new browser test RED→25 current Auth/session E2E PASS;
  no automatic retry,fields preserved,timer disposed on unmount.
- Native Linux Uvicorn signal smoke PASS:drain rejects messages/readiness503,live200,
  cancel still401 without authentication;SIGTERM cleanup marker observed in0.215s.
  No active turns/DB/worker fence/rollback tested by that smoke.
- SES C02a explicitly approved and executed:one Gmail EMAIL_ADDRESS identity verified
  SUCCESS via the authorized mailbox. Sandbox/quota/SMTP/DNS/IAM/runtime unchanged.

Ruling: reset commits the local auth-version fence before remote PUT and re-verifies the
recovery token before mutation. A rejected or uncertain update can leave old local
sessions logged out. This conservative recovery path avoids a changed password with
unrevoked local sessions; it costs an extra read-only provider check and possible re-login.

Ruling: after a committed login whose session view fails, retain the unissued session
until expiry and allow a fresh login. Do not sign out a provider session without proving
it is unused by another valid local session. Fault responses issue no cookies;no raw
opaque token is retained for recovery. Cost:bounded orphan rows until retention/expiry.

Ruling: keep opaque identity outcomes on a narrow error-code allowlist;configuration,
validation or unknown resend/recovery4xx return safe availability failure instead of sent.
Use bounded static metric categories,not raw bodies/codes. Current contract was checked
against [Supabase error codes](https://supabase.com/docs/guides/auth/debugging/error-codes)
and its [resend](https://github.com/supabase/auth/blob/master/internal/api/resend.go)/
[recovery](https://github.com/supabase/auth/blob/master/internal/api/recover.go) source.
Risk:an unrecognized future identity-specific error may become an availability failure;
update the allowlist only with enumeration-safe provider evidence.

Ruling: queue local AI message admission before database checkout under the existing
candidate dispatch flag. Profiling observed3 checkouts waiting for the same advisory lock.
Keep the PostgreSQL lock as global authority. Initial width1/15s admitted37/50 and rejected13;
it did not meet the workload. Width2 đã được thử (leaves up to3 local checkouts for other work),
queue≤100,wait≤min(15s,turn timeout),fresh auth after wait and drain recheck. Default flagfalse.
Risk:queueing can increase admission latency and rejects overloaded traffic;it is process-local,
does not coordinate replicas and must pass load/UI timing gates before activation.

Final: Ruling: unsupported public search fails closed with candidate dispatch enabled;
the cost is feature unavailability until its paid-operation authority is integrated.
Final: Ruling: review did not establish cloud quotas/pricing/mixed capacity;these remain
release blockers. Regression counts never substitute for hosted evidence.
Final: minor (deferred): no Minor findings were reported by the fresh reviewer.


Ruling: the admission-before-checkout experiment was REMOVED after measured regressions:
width1 accepted37/50,width2 accepted33/50 with15s deadline. It reduced pool waiting but
rejected legitimate traffic and did not solve CPU/query pressure. Both source additions
and their experiment-only test were removed;all RED/GREEN/load artifacts remain.
Current candidate keeps PostgreSQL admission and the physical model gate. Do not raise
queue deadlines above the frontend20s timeout or increase pools merely to hide failure.
Cost of rollback:the original measured database pressure remains unresolved.


## Execution update — 2026-11-05T15:26:44.797Z

- The 41 original task IDs and the existing ledger counts (2 DONE, 27 IN_PROGRESS, 7 BLOCKED, 2 FAILED, 3 DEFERRED) were preserved. No cloud evidence or source implementation was promoted to a production PASS.
- Test-only fixes were pushed to `feat/upgrade-user`: `d655ee86` passes `dispatch_enabled=False` through the collaboration test wrapper; `48a1df2f` raises the cancellation-start wait from 3s to 10s; `fdb5dc98` supplies `ai_dispatch_gate_enabled=False` in the web-search mock. No product runtime code changed in these three commits.
- GitHub Actions run #365 for `fdb5dc9897562b0d8550058218f7579411b1c2c5` was IN_PROGRESS at capture time; backend checks against disposable PostgreSQL were still running. Runs #363 and #364 had completed with failure in that backend-check step. Do not claim a green candidate until #365 and the latest post-documentation run finish successfully.
- Cloud review confirmed the running Sydney EC2 target and account/project fingerprints; billing permission, OpenAI staging-project selection, Supabase email-send rate, and complete recovery readiness remain unresolved. Detailed read-only values and gaps are recorded in documents 13–16.
- The exposed `postgres` migration-owner credential was not rotated. The project Database Settings page confirms reset will break existing connections. Rotation remains blocked pending owner approval and a secure owner-entered reset; the separate runtime credential was not changed.
- Release remains **NO-GO**. No hosted Auth/SMTP/security setting, database migration, SES request, paid backup, alarm, deployment, restart, resize, or merge was performed.
