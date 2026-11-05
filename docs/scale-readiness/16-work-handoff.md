# MoodPrint — execution handoff to ChatGPT Work

Updated 2026-11-05. **Release NO-GO. Feature-branch push is not deployment approval.**
Shared source: [feat/upgrade-user](https://github.com/mhiu05/MoodPrint/tree/feat/upgrade-user).
Use the implementation SHA recorded in [17](17-work-execution-prompt.md), then read the
latest branch tip for documentation corrections. Read [12](12-implementation-progress.md)
for all 41 original IDs and [15](15-test-results.md) for actual tests and limits.

## Access, identity and authority

- Application stays **https://moodprint.duckdns.org**. Do not buy a domain or service.
- AWS account **…3536**, region **ap-southeast-2**, instance **i-0664d6ea5930452db**,
  Name=moodprint-staging, Application=MoodPrint, Environment=staging. Current state:
  **running m7i-flex.large**, EIP **13.210.93.93**, allocation **eipalloc-0c23e4fdcdce12bc9**.
- Supabase project fingerprint **44a655e04517**, Pro, Tokyo/ap-northeast-1,
  PG17.11, migration head0029_journal_intelligence. Select the project whose configured
  URL SHA256 first12 characters equal that fingerprint (same convention as inventory).
  Do not guess a project by its display name; use Project Settings → General reference
  plus the owner's secure deployment configuration to verify the mapping.
- OpenAI: project attached to the staging runtime key. Project/org ID **UNKNOWN**;
  establish it through the owner's secure project selection before any paid dispatch.
  A successful model lookup is not proof of quota, pricing or ownership.
- Work's cloud browser has a **separate login session from the owner's Chrome**.
  Request secure sign-in/MFA when necessary, never passwords, keys or recovery codes
  in chat. If the existing Chrome login is necessary, use a supported Chrome
  integration with the owner's permission. Do not assume access to `E:\MoodPrint`.
  Use pushed GitHub files; local evidence not published is explicitly identified below.
- Read-only investigation and local/mock engineering are authorized. Only the named
  instance's conditional Start was additionally authorized; it is already running.
  Do not stop/restart/resize it or deploy a new image under that permission.
- Every action marked **REQUIRES_OWNER_CONFIRMATION** needs its own specific approval.
  Prepare exact target, old/new configuration, cost, downtime, verification and rollback
  before asking. Do unrelated read-only work while a decision is pending.
- Preserve confirmation, CAPTCHA, ownership, consent, financial holds and release hold.
  Never paste secret values, journal/media/chat data, tokens or raw sessions into evidence.

## 1. AWS SES production access and sending quotas

| Field | Actionable record |
|---|---|
| Task ID / Status | P0-H03, P1-A08/A09, P3-I09; **BLOCKED** for hosted activation |
| Problem | SES remains sandbox:200 recipients/24h,1/s; SentLast24Hours1; sending enabled; one EMAIL_ADDRESS identity SUCCESS. Insufficient evidence for public signup or NAT100 email throughput. |
| What Codex tried | `aws sesv2 get-account --region ap-southeast-2`; `list-email-identities` with type/status-only query; no application mail sent this round. |
| Evidence | [round2-cloud.json](evidence/round2-cloud.json), [SES prior identity](evidence/ses-canary-identity.json), [13](13-cloud-inventory-redacted.md). |
| Target website / Account | [SES Sydney](https://ap-southeast-2.console.aws.amazon.com/ses/home?region=ap-southeast-2), AWS…3536. |
| Required action | Account dashboard → Get set up → Request production access. Read current form and prepare transactional use-case: explicit user signup/recovery, confirmed email, CAPTCHA/rate limits, suppression and bounce/complaint handling. Website=moodprint.duckdns.org. Disclose verified Gmail sender and unresolved alignment; do not invent a domain. Read sending quota, reputation and case status. Separately inspect Service Quotas → Amazon SES → daily sending quota/sending rate. Proposed initial capacity review:at least5recipients/s and3000/day, subject to actual workload and safeguards. |
| Permissions | Read pages immediately after sign-in. **REQUIRES_OWNER_CONFIRMATION** before submitting production-access/quota requests, enabling configuration sets or event destinations. |
| Cost/downtime | Read-only $0; requests can enable billable sending. Sending/event charges need current region quote; no application downtime expected for request submission. |
| Success criteria | Console and `GetAccount` agree production_access=true, approved numeric quotas recorded; reputation/suppression/events reviewed; this alone does not pass delivery gates. |
| Rollback | Do not send until SMTP approval. Pause new application mail if failure/abuse; retain suppression and event history. Production access cannot be described as an application rollback. |
| Next step | Sign in, capture redacted Account dashboard/quota facts and draft the exact request for owner review. |

## 2. Sender without a custom domain

| Field | Actionable record |
|---|---|
| Task ID / Status | P1-A08, G04/G05; **BLOCKED** for reliable public delivery |
| Problem | An individually verified address can meet SES sender-identity authorization. After production access, SES permits unverified recipients. Neither fact proves DMARC alignment, reputation or inbox delivery for Gmail From. |
| What Codex tried | Read official SES identity/sandbox/DMARC and Gmail sender guidance; DNS TXT lookup `_dmarc.gmail.com` returned `v=DMARC1; p=none; sp=quarantine; ...` on2026-11-05. No domain purchase, DNS mutation or mail send. |
| Evidence | [AWS DMARC](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html), [sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html), [Gmail policy](https://support.google.com/mail/answer/81126), [sender facts](evidence/round2-sender-policy.json). |
| Target website / Account | SES…3536/Sydney → Configuration → Verified identities → existing Gmail identity; owner's controlled receiving mailbox. |
| Required action | Inspect identity DKIM/MAIL FROM without changing it. For an authorized low-volume test to already verified owner-controlled recipient, inspect Authentication-Results:SPF domain, DKIM d=, RFC5322.From, DMARC result/alignment, Return-Path, mailbox spam placement, latency and SES delivery/bounce events. Redact addresses/message IDs and keep only aggregate results. Verify current provider policy and actual quotas again. |
| Permissions | Read-only authorized; existing verified Gmail identity may be used for carefully controlled tests within SES restrictions. Production SMTP, new recipients/identities, domain/DNS and paid services remain **REQUIRES_OWNER_CONFIRMATION**. |
| Cost/downtime | A few bounded messages incur small sending charges; record current pricing first. No bulk cohort or paid purchase authorized by a canary. |
| Success criteria | Actual headers prove alignment and provider policy permits usage; quota, reputation and inbox results meet agreed delivery targets. Gmail p=none is not DMARC pass. Without DNS authority for gmail.com, ordinary SES SPF/SES DKIM cannot be assumed aligned with Gmail From. |
| Rollback | Stop mail tests; retain existing verified identity and suppression. Do not disable confirmation. |
| Next step | Inspect identity and headers of an allowed controlled test. If alignment fails, propose an owner-controlled sending domain/subdomain:registrar purchase separately approved → DNS records → SES domain identity/Easy DKIM → optional MAIL FROM MX/SPF → DMARC → verify headers. Website URL can stay DuckDNS. A DNS provider/domain option must be priced and approved before purchase. |

This is a technical distinction: **SES authorization is potentially satisfiable with
email-address verification; dependable public transactional delivery is unproven.**
The alignment problem is why a separately controlled sending domain is the recommended
fallback, not a prerequisite for unrelated coding or read-only investigation.

## 3. Supabase custom SMTP and Auth limits

| Field | Actionable record |
|---|---|
| Task ID / Status | P1-A01/A02/A03/A06/A08/A10, P0-H03; **IN_PROGRESS/BLOCKED** |
| Problem | Hosted SMTP, CAPTCHA provider/origins, Auth limit values and forwarding remain unknown. Public settings show confirmation enabled. Current deployed API has global10/$20 settings, not candidate50/$50. |
| What Codex tried | Public Auth settings read; local fake CAPTCHA/Auth NAT100/distributed100 passed previously; retry/timeout/reset-fence/negative tests run. SSM numeric allowlist and public endpoint checked this round. |
| Evidence | [provider-readonly.json](evidence/provider-readonly.json), [round2-cloud.json](evidence/round2-cloud.json), [15](15-test-results.md), frontend Auth source/tests. |
| Target website / Account | [Supabase Dashboard](https://supabase.com/dashboard), matching project fingerprint44a655e04517. |
| Required action | Authentication → Email/SMTP Settings (or Email Templates → SMTP, depending current navigation):read custom SMTP host/port/TLS/sender without exposing password. Authentication → Rate Limits:record email/hour and applicable IP/action limits. Authentication → Attack Protection/CAPTCHA:provider/site origin and enabled state. URL Configuration:site URL and redirect allowlist. Providers → Email:confirm-email remains enabled. Inspect IP Address Forwarding setting; no setting change yet. |
| Permissions | Read-only after sign-in authorized. SMTP/forwarding/rate/CAPTCHA/policy changes are **REQUIRES_OWNER_CONFIRMATION**. |
| Cost/downtime | Investigation $0. SMTP/auth changes affect signup/recovery delivery; rate increases expose abuse/SES cost. Approval must include tested sender/quota and exact old/new settings. |
| Success criteria | Effective hosted configuration captured safely, legitimate NAT100 demand fits all bottlenecks, CAPTCHA and negative cases still deny abuse. Trusted proxy must strip client-supplied forwarding headers. |
| Rollback | Restore reviewed prior SMTP/rate/forwarding settings from vault; retain suppression/confirmation and all session fences; no replay of outcome-unknown signup/reset. |
| Next step | Read values and upstream key category. Supabase forwarding requires a server-side secret API key plus explicit enablement; publishable/legacy anon/service_role are not supported by current docs. Do not substitute an admin bypass or auto-confirm users. |

[Current Supabase rate-limit documentation](https://supabase.com/docs/guides/auth/rate-limits)
must be read with account facts; defaults are not this project's actual limits.

## 4. OpenAI project limits, pricing and model access

| Field | Actionable record |
|---|---|
| Task ID / Status | P3-I01/I02/I03/I06/I09, G07/G09; **BLOCKED** for real campaign |
| Problem | Model GET was200 for gpt-6-luna; actual org/project/model RPM/TPM, spend, access to input-count endpoint, fees and price multipliers are unverified. |
| What Codex tried | Model metadata GET only in prior round; read official Luna/pricing/count docs. No generation/judge calls. Added durable campaign primitive and25 offline tests. |
| Evidence | [provider-readonly.json](evidence/provider-readonly.json), [campaign runbook19](19-paid-campaign-runbook.md), [round2-campaign-summary.json](evidence/round2-campaign-summary.json), [Luna docs](https://developers.openai.com/api/docs/models/gpt-6-luna). |
| Target website / Account | [OpenAI platform](https://platform.openai.com), owner's staging project selected securely; org/project ID currentlyUNKNOWN. |
| Required action | Settings → Organization → Projects → intended staging project → Limits:read gpt-6-luna/shared-family RPM/TPM, project permissions and budget notification behavior. Organization → Billing/Usage:read remaining credits/current spend. Open current Luna pricing, including service tier, long context, regional and cache-write premiums. Verify model key permissions and input-count endpoint availability/price without generation. Record sanitized project fingerprint and dated rate table. |
| Permissions | Read-only authorized. Existing $3 cumulative staging generation campaign is approved, only gpt-6-luna, zero judge API; all prerequisites must be met first. Project limit/budget changes or production $50 activation are **REQUIRES_OWNER_CONFIRMATION**. |
| Cost/downtime | Metadata read no generation. Counting may have unknown fees:verify before calling. Total paid campaign liability must remain≤$3 across restarts/retries, not $3 per run. |
| Success criteria | Account-specific dated facts plus canonical durable ledger, immutable counted payload and bounded one-wire transport; application pooled/all-provider gaps resolved before a global hard-cap claim. |
| Rollback | Stop new admissions; retain reserved/unknown liability and ledger. Never reset daily/campaign totals to fit another run. |
| Next step | Establish account mapping and record numeric limits. Return these facts to engineering; do not press Playground Generate as a quota check. |

## 5. Database credential rotation

| Field | Actionable record |
|---|---|
| Task ID / Status | P0-H02/C01, G02; **BLOCKED** |
| Problem | Active postgres migration-owner password in untracked backend/runtime.txt. Role has CREATE ROLE/DB and BYPASSRLS; not the moodprint_backend runtime password. |
| What Codex tried | Read without printing value; exact-password current tracked-content scan found no match; TLS login with READ ONLY catalog SELECT succeeded; compared local consumer categories and SSM version26 without emitting DSNs/secrets. |
| Evidence | [round2-security.json](evidence/round2-security.json), [exact procedure20](20-security-cloud-actions.md), [safe inspector](../../scripts/inspect_credential_exposure.py). |
| Target website / Account | Supabase matching project; password manager; CI/IDE/admin consumers; AWS SSM/moodprint/staging/runtime only if a dependency is discovered. |
| Required action | Follow doc20 steps1–7:independent Dashboard/MFA recovery → freeze migration/admin jobs → inventory external consumers → new password in vault → reset project Database password → replace only migration DSNs → new credential READ ONLY/TLS PASS and old credential REJECTED on fresh connections → runtime health → approved plaintext cleanup. Do not run configure_database.py wholesale; it can overwrite both DB URL fields. |
| Permissions | Read-only investigation authorized. Reset/consumer update/connection termination/plaintext deletion: **REQUIRES_OWNER_CONFIRMATION**. |
| Cost/downtime | Password reset itself not quoted as a new paid service. Migration/admin clients briefly unavailable; runtime expected independent, but verify and prepare incident window. Existing authenticated sessions may persist after reset. |
| Success criteria | All owner consumers mapped; new positive/old negative authentication, correct TLS/role; runtime new connections and ready200; no secret in Git/logs. A timeout is not evidence old password revoked. |
| Rollback | Keep admin jobs stopped, recover through Dashboard and reset to another NEW secret if necessary. Never restore exposed password; do not mass-kill managed-service connections. |
| Next step | Owner confirms independent admin recovery and exact reset scope; then execute doc20 in a secure session. No full runtime restart is proposed based on current SSM mapping. |

## 6. Supabase compute/pooler/backup review

| Field | Actionable record |
|---|---|
| Task ID / Status | P2-D01/D02/D06/D08/D09/D10, P0-H02; **IN_PROGRESS/BLOCKED** |
| Problem | Pro plan verified, compute SKU/pooler client/backend caps/actual backups/PITR/restore unknown. DB backup excludes private object bytes and custom-role passwords. |
| What Codex tried | Read-only PG catalog:max60/runtime role20, sample RLS/grants, private6objects~9.47MB; selected recovery policy;22 verifier tests and synthetic isolated pg_dump/pg_restore rehearsal. Latest target EBS snapshot query returned zero. |
| Evidence | [13](13-cloud-inventory-redacted.md), [recovery runbook18](18-recovery-runbook.md), [rehearsal](evidence/round2-recovery-rehearsal.json), [verification](evidence/round2-recovery-verification.json). |
| Target website / Account | Supabase matching project → Settings/Compute and Disk, Connect, Database → Backups; AWS EC2 → Volumes/Snapshots for exact staging volume. |
| Required action | Read compute SKU/memory/connection limits, direct/session/transaction endpoints and caps. Record current Pro7-daily-backup availability/latest capture and PITR state. Review Storage private inventory count/bytes, not contents. Select encrypted independent destination/key recovery owner and quote12h DB/object/config capture,7daily EBS versions. Prepare isolated restore to NEW targets following18. |
| Permissions | Read-only/local synthetic authorized; RPO24h/RTO8h policy chosen autonomously. Paid jobs/copies/projects/snapshots or hosted restore: **REQUIRES_OWNER_CONFIRMATION**. Never restore into production. |
| Cost/downtime | Price storage/egress/requests/snapshots/new recovery project/temporary host before activation. Recovery rehearsal must have test-only endpoints; avoid real recipients and provider calls. |
| Success criteria | Complete retained generation≤24h, freshness alert at18h, decrypt/read permission, DB+objects+configuration+secrets+EBS restored and application/privacy/financial invariants verified within measured8h. Targets remain unachieved until hosted rehearsal. |
| Rollback | No production replacement. Fence/disable isolated target and clean only approved test resources after evidence; retain existing backups. |
| Next step | Read actual backup list/compute/pooler caps, then quote one exact encrypted destination and isolated rehearsal proposal. |

## 7. CloudWatch alerts and notifications

| Field | Actionable record |
|---|---|
| Task ID / Status | P4-E03/P0-H03, G13; **IN_PROGRESS** |
| Problem | Existing templates and content-free metrics are partial; alarm/channel delivery and metric dimensions unknown; no prefixMoodPrint alarms in earlier snapshot. |
| What Codex tried | AWS alarm inventory; read agent/alarm templates; added allowlist-only runtime diagnostic. Did not read private log bodies or create alarms/subscriptions. |
| Evidence | [runtime diagnostic](evidence/tools/round2-runtime-diagnostic.py), [cloud snapshot](evidence/round2-cloud.json), [existing alarm proposal](../../deploy/aws/cloudwatch-alarms.json), [agent](../../deploy/aws/cloudwatch-agent.json). |
| Target website / Account | AWS…3536/Sydney → CloudWatch → Metrics/Alarms/Log groups; SNS → Topics → approved operator destination. |
| Required action | Verify log group/agent delivery and exact dimensions. Prepare alarms:EC2 StatusCheckFailed>0 for2×60s; CPU>80% for5×60s (Flex baseline implications); host memory>80% and disk>80% for3×60s using actual CWAgent dimensions; HTTP5xx/failed AI/pool timeout counts, readiness; reserve/budget denials and backup age. Inspect metric emission before alarm creation. Pool p95<100ms and loop lag require numeric distributions, not counting text lines. Propose missing instrumentation separately. |
| Permissions | Read-only authorized. New billable filters/alarms/SNS subscription/test notification: **REQUIRES_OWNER_CONFIRMATION** with destination, retention, monthly estimate and approved test recipient. No unsolicited messages. |
| Cost/downtime | CloudWatch ingestion/custom metrics/alarms/SNS can cost money; no app downtime expected for monitoring-only changes. |
| Success criteria | Each metric exists with correct unit/dimensions/aggregation, no PII labels; approved canary reaches intended recipient; missing-data behavior and alarm recovery verified. |
| Rollback | Disable newly approved alarm actions/revert config; preserve evidence/log retention and avoid deleting existing alarms/backups. |
| Next step | Read current agent/log delivery and list matching metric dimensions; prepare priced config diff and notification destination for confirmation. |

## 8. EC2 staging verification

| Field | Actionable record |
|---|---|
| Task ID / Status | P4-E01/E02, P0-H01, G12/G14; **FAILED/IN_PROGRESS** for capacity/rehearsal |
| Problem | Correct host is running/healthy, but no target-size50-user soak, restart/drain/fencing/rollback or historical resource proof. Public real-user traffic role unknown. |
| What Codex tried | STS; DescribeInstances/Types/Status/AMI/Volumes/Addresses; SSM diagnostic Success; DNS/TLS and HTTP probes; TCP22 timed out. No Start needed; no restart/deploy. |
| Evidence | [round2-cloud.json](evidence/round2-cloud.json), [20](20-security-cloud-actions.md), [15](15-test-results.md). |
| Target website / Account | AWS…3536/Sydney → EC2 → Instances → i-0664d6ea5930452db; Systems Manager → Fleet Manager/Session Manager. |
| Required action | Confirm current tags/type/status/EIP again; review aggregate request/5xx and billing metrics to establish real traffic. Inspect cgroup CPU throttling/OOM/restarts/CPU and memory duration metrics with no private payload. EC2 Monitor tab for per-instance history; Billing/Cost Explorer for actual SKU/free-tier/credit applicability. M7i-flex is not T3-credit billed; Flex baseline40% is not guaranteed full sustained2vCPU. Record price/discount status rather than infer free use. |
| Permissions | Read-only authorized. Named conditional Start already satisfied by existing running state; no Stop/resize/restart/deploy permission. **REQUIRES_OWNER_CONFIRMATION** for disruptive rehearsal or new infrastructure. |
| Cost/downtime | Running EC2/EBS/EIP already incur applicable charges. Price List API:Linux/shared m7i-flex.large Sydney$0.1197/h (~$87.38/730h compute only); EBS/IPv4/network/tax additional. Actual credits/discounts remain unverified. No incremental resource created. Restart on single host disrupts service. |
| Success criteria | Correct identity, existing EIP, healthy checks and SSM; then target-size measured50 workload/900s and2h mock, no pool timeout/OOM/unplanned restart; approved active-turn drain/rollback meets measured recovery target. |
| Rollback | Diagnostic needs none. Deployment needs independently approved compatible prior image/env and worker fence; retain all holds, no schema downgrade. |
| Next step | Read aggregate traffic/billing/cgroup data. Return resource envelope to coding; do not deploy feature-branch image to obtain measurements without approval. |

## 9. Hosted Auth/email canary

| Field | Actionable record |
|---|---|
| Task ID / Status | P1-A06/A07/A09/A10/P5-L02, G03/G04/G05; **IN_PROGRESS/BLOCKED** |
| Problem | Local admission/cooldown/provision tests do not establish actual SMTP delivery, confirmation, login, recovery or safe duplicate outcomes. |
| What Codex tried | Synthetic distributed100/NAT100 passed previously; current Auth/session/privacy regression; frontend typecheck/unit. No hosted Auth identity created this round. |
| Evidence | [15](15-test-results.md), [Auth source](../../backend/app/modules/auth/routes.py), [Auth reliability tests](../../backend/tests/test_scale_auth_reliability.py). |
| Target website / Account | MoodPrint staging, Supabase Auth matching project, SES Sydney, owner-controlled verified test mailbox. |
| Required action | First determine actual SMTP routing. Prepare one test address/recipient allowlist, maximum5mail events, real CAPTCHA and expected confirmation URL. Signup→mail accepted→delivered→click once→confirmed→login→app session/provision1User/4Consent. Check resend cooldown, duplicate signup opaque response, expired/used link and recovery/logout. Do not simulate network timeout by retrying an ambiguous real signup. Capture event timing/category only, no tokens/raw emails. |
| Permissions | Investigate/read now. Existing controlled Gmail/SES restriction authorization applies only to allowed recipients. New hosted account/policy/SMTP activation/cohort or destructive cleanup: **REQUIRES_OWNER_CONFIRMATION** with exact manifest. |
| Cost/downtime | Small bounded mail quota/charge; no AI. Sandbox cannot send to unverified recipients. No100-user hosted cohort until quota/sender alignment/delivery/abuse readiness is established. A custom domain is a fallback, not a mandatory purchase. |
| Success criteria | Real lifecycle verifies confirmation remains required, correct session/provision after duplicate recovery; header alignment/mail timelines and negative abuse tests pass. Separately approve full100distributed/NAT cohorts. |
| Rollback | Stop arrivals, preserve ambiguous outcome and suppression; revoke only owned test sessions/cleanup exact approved actors. Do not weaken CAPTCHA or auto-confirm. |
| Next step | Read SMTP mapping, then prepare the single-mailbox canary manifest and owner confirmation for hosted writes. |

## 10. Real AI staging tests under the $3 cap

| Field | Actionable record |
|---|---|
| Task ID / Status | P3-I02/I06/I07/I08/I09/P5-L01/L02, G07/G08/G09; **BLOCKED** for paid run |
| Problem | Canonical ledger primitive now exists, but no reviewed immutable-payload/exact-count/one-wire live adapter. Workflow pooled allocation and registered Voyage/STT coverage incomplete; fake sustained-load evidence does not close capacity. |
| What Codex tried | Campaign25 offline tests incl12-process race/crash; financial regression; fake50/900s attempts recorded in15; zero generation/judge APIs. |
| Evidence | [campaign19](19-paid-campaign-runbook.md), [controller](../../scripts/paid_campaign.py), [budget query regression](../../backend/tests/test_scale_budget_queries.py), [15](15-test-results.md). |
| Target website / Account | OpenAI staging project once verified; reviewed isolated staging app; coding environment with one durable campaign file. |
| Required action | Finish coding prerequisites before paid test. Use one campaign ledger forever for this campaign, reserve maximum price before every physical call and never refund uncertain/crash/cancel outcomes. Only gpt-6-luna generation; no judge API. Confirm no hidden retry/hosted tool/fanout. First tiny synthetic nonprivate sample, coding agent judges saved sanitized outputs directly. Calculate whether a50concurrent/900s profile fits remaining liability; if not, report scope not affordable, never exceed$3 or reset ledger. |
| Permissions | $3 cumulative staging campaign already approved; no need to ask for that decision again. Actual project/target/account facts and safe adapter are prerequisites. Production deploy/$50 cap/limits changes remain **REQUIRES_OWNER_CONFIRMATION**. |
| Cost/downtime |≤$3 cumulative known+reserved+unknown campaign liability, including any count fees. Existing snapshot0calls/$0spent. Target deployment/restart is not implicitly approved. |
| Success criteria | All wire calls reserved once, counted payload bound enforced, model/tier/pricing known, actual usage/cost reconciled, campaign no overspend; quality/privacy/consent tests pass and required concurrency profile honestly reported. |
| Rollback | Stop admissions, retain ledger and unknown holds; cancel owned test runs through approved control; no refund on EOF. |
| Next step | Browser reads project facts; coding agent completes live adapter and pooled/all-provider coverage, reruns local gates, then runs approved bounded campaign. |

## 11. Remaining 41-task implementation work

This table retains every original ID and canonical status. **DONE** tasks have a
maintenance follow-on, not missing original acceptance. Optional tasks retain
**DEFERRED** status; every unresolved mandatory item is BLOCKED/FAILED/IN_PROGRESS.
`L0` means a newly owned disposable
local database with egress denied. No cloud browser can run local Windows commands.
Use a supported coding environment/agent for rows marked Coding.

| Task ID | Status | Problem | What Codex tried | Evidence | Target website | Account/project | Required action | Permissions | Cost/downtime | Success criteria | Rollback / Next step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0-H01 | IN_PROGRESS | Hosted facts incomplete | STS/EC2/SSM/model/catalog reads |13;round2-cloud.json | AWS/Supabase/OpenAI | fingerprints above | Sections1,3,4,6,8 | Read-only/sign-in |$0read | All limits dated/mapped | No mutation;read Limits next |
| P0-H02 | BLOCKED | Active exposed owner secret/recovery | TLS readonly login;local restore |20;18;round2-security.json | Supabase/vault |44a655e04517 | Section5 rotation+6restore | REQUIRES_OWNER_CONFIRMATION | Admin interruption;restorecost | Oldreject/newpass;hostedrestore | Newsecret recovery;inventory external consumers |
| P0-H03 | BLOCKED | SMTP/quota/alerts unknown | SES reads;identitystatus |13;16sections1/3/7 | AWS/Supabase |…3536/projectfingerprint | Read policies then exact changes | Read now;changes need confirmation | Sending/monitoringcharges | Auth mail+alerts verified | Restore priorconfig;read dashboards |
| P1-A01 | IN_PROGRESS | Baseline hosted Auth missing | SSM numeric/runtime/public reads |round2-cloud.json | Supabase |44a655e04517 | Read SMTP/rates/redirects | Read-only/sign-in |$0 | Effective values frozen | Nochange;section3 |
| P1-A02 | IN_PROGRESS | NAT policy hosted validation |100/100fake NAT | T3-local.json;12 | Coding/Supabase |L0/project | Retain abuse controls;real cohort | Code authorized;hosted change confirmation | Mailcharges | NAT100confirmed+negative abuse | Flagfalse;section9 |
| P1-A03 | IN_PROGRESS | Egress/forwarding proof absent | Spoof headertests;SSM reads |12;15 | Supabase/EC2 | project/targetEC2 | Trace trusted proxy to provider;read forwarding | Read-only first |$0read | No spoof/IPcollapse | Keep publishable mode;section3 |
| P1-A04 | DONE | TLSreuse follow-on |80burst20warm TCP lifecycle | auth-tcp-pool.log;15 | Coding |L0 | Preserve pooled lifecycle;optional TLSbenchmark | Local authorized |$0external | No bearer/cookie leak/closed sockets | Revert poolchange if regression;no mandatory retest |
| P1-A05 | DONE | Hosted provider follow-on | Retry-After/unknown mapping/UI25E2E |15 | Supabase/application |project/staging | Hosted cooldown/mailcanary | Section9 confirmation | Boundedmail | No false sent/autoreplay | Prior reviewedconfig;section9 |
| P1-A06 | IN_PROGRESS | Full ambiguity/CAPTCHA matrix | Reset fence DB/commit/lostreply tests | round2-regression.log;15 | Coding/Supabase |L0/project | Finish ambiguous signup UX matrix then real recovery | Coding;hosted confirmation |$0mock | No duplicate/unsafe PUT or cookies | Retain committed fence;section9 |
| P1-A07 | IN_PROGRESS | Provision timing/lock distribution | Fault+duplicate provisiontests |15;round2-regression.log | Coding |L0 | Benchmark distinct/duplicate first-login p95/p99 | Local authorized |$0 |1User/4Consent;boundedpool | Revert timingcode;run separate provisionprofile |
| P1-A08 | BLOCKED | SES/SMTP/delivery alignment | Verified Gmail identity+quota reads |13;section2 | AWS/Supabase |…3536/project | Sections1–3 | Reads now;activation confirmation | Sendingcharges | Real headers/delivery/quota | Stop mail;inspect identity |
| P1-A09 | BLOCKED | Mail event sink/lifecycle absent | Inventory only |12;section7/9 | AWS/Coding |…3536/L0 | Implement dedup/out-of-order event fixtures;approve sink | Code authorized;sink confirmation | Eventstoragecharges | Delivered≠confirmed;noPII | Revert new sink;code fixtures first |
| P1-A10 | IN_PROGRESS | Real signup follow-on absent |100distributed/NATlocal | T2-local.json;T3-local.json | Supabase/app |project/staging | Section9 then approved cohort | Hostedwrite confirmation | Mailquota/charges |100complete real lifecycle | Stoparrivals;singlecanary first |
| P1-A11 | DEFERRED | Optional alternative unneeded | No queue added |03;12 | Coding |L0 | Revisit only measured quota failure | No activation approval | Designcost unknown | Evidence justifies alternative | Keep existingstack;finish quota facts |
| P2-D01 | IN_PROGRESS | Compute/pooler caps unknown | Catalog role20/server60 |13 | Supabase |project | Section6 dashboard | Read-only/sign-in |$0 | Correct server/client budgets | No topologychange;read Connect |
| P2-D02 | IN_PROGRESS | Deploy effective budget rejection missing | Calculator steady8/overlap16+reserve4 | database/budget.py;15 | Coding/EC2 |L0/target | Wire prelaunch check against verifiedlimits | Code only;deploy confirmation |$0local | Reject unsafe effectiveoverride | Previousconfig;implement deployment gate |
| P2-D03 | IN_PROGRESS | Checkout/CPU pressure unresolved | Poll4→3,liability5→1;soak attempts | round2-T4 reports;15 | Coding |L0 | Profile remaining admissions/transactions and targetRTT | Local mock authorized |$0external | No pooltimeout;p95<100ms | Revert optimization if privacy/moneyfail;read latestreport |
| P2-D04 | IN_PROGRESS | Bounded waits not all jobs | SET LOCAL and503tests |15;config.py | Coding |L0 | Extend waits with cancellation faulttests | Local authorized |$0 | No unbounded lock/statebleed | Flagfalse;measure each jobpath |
| P2-D05 | IN_PROGRESS | First-login distribution missing |100firstlogin integrity |15 | Coding |L0 | Separate provisioning latency/pool dataset | Local authorized |$0 | p95/p99+duplicates evidence | Keep schema;build profile |
| P2-D06 | IN_PROGRESS |90day plans missing | Advisor;inbox p95recheck |13;15 | Coding/Supabase |L0/project | Seed skew90day;EXPLAIN before indexes | Local authorized;hostedDDL confirmation |$0local | Measuredquery/growth headroom | No indexchange until evidence;seed |
| P2-D07 | IN_PROGRESS | Retention transactions/session TTL | Hold-preservation regressions | test_scale_retention_safety.py | Coding |L0 | Choose bounded sessionTTL and batchtransaction budgets | Local code authorized |$0 | No liability/cascade loss | Never restorepurgeddata as rollback;design TTL |
| P2-D08 | IN_PROGRESS | Full cross-user/grants matrix missing | Sample catalog/RLS/privacy tests |13;round2-regression.log | Coding/Supabase |L0/project | Full role/exposure/cross-user matrix | Read-only/code |$0 | No browser/private escape | No newgrants;complete matrix |
| P2-D09 | DEFERRED | Pooler topology benefit unproven | prepare_threshold=None kept |04;12 | Supabase/Coding |project/L0 | Read modes/caps;change only after benefit | Read now;topology confirmation | Potential downtime | Poolingcompatibility+benefit | Existing endpoint;section6 |
| P2-D10 | BLOCKED | Hosted complete recovery untested | Policy/verifier22/localrestore |18;recovery JSON | AWS/Supabase |project/targetEC2 | Section6 costed isolatedrehearsal | REQUIRES_OWNER_CONFIRMATION | Storage/egress/testhost | RPO24h/RTO8h measured | Never replaceprod;quote destination |
| P3-I01 | IN_PROGRESS | Exact release digest/quotas unknown | Runtime allowlist;Dockerimage IDs | round2-cloud.json | EC2/OpenAI |target/projectunknown | Read registry attestation/projectmapping | Read-only |$0 | SHA/digest/env same candidate | No deploy;read provenance |
| P3-I02 | IN_PROGRESS | Pooled parent/child allocation missing | Per-row bound/oneSQL liability | accounting.py;15 | Coding |L0 | Implement pooled worstcase allocation+fanouttests | Code authorized;flagoff |$0mock | All children bound;unknownretained | Legacyholds;design pooledledger |
| P3-I03 | IN_PROGRESS | Lane fairness/crossprocess quota proof | Dispatch gate+postqueuefences | dispatch.py;15 | Coding/EC2 |L0/target | Fanout/background targetload+headers | Code;stage activation confirmation |$0mock | Physicalcalls andparents separate | Flagfalse;run fake mixedprofile |
| P3-I04 | IN_PROGRESS | Complete stage metric timeline missing | Pool/loop/RSS/parent counters | scale_readiness.py;15 | Coding |L0 | Instrument finite stagehistograms noPII | Code authorized |$0mock | PhysicalHTTP/SDK/client labelsaccurate | Revert metrics only;build contract |
| P3-I05 | IN_PROGRESS | NetworkSSE/slowreader/restart missing | ASGI50 and lifecycle unit |15;streams.py | Coding/Caddy |L0 | Caddy/TLS sockettest+disconnect/replay/finite lifetime | Local authorized |$0 | No leak/orphans/duplicate charge | Preserve holds;build networkfixture |
| P3-I06 | IN_PROGRESS | Registered Voyage/STT paid scope open | Guest/subset/dispatch tests |12;19 | Coding |L0 | Bound+reserve every paid scope;poolVoyageclient | Code authorized |$0mock | Globalcap actually covers allpaid | Keep flagsfalse;enumerate wireclients |
| P3-I07 | FAILED | Sustained50/SLO not established | Full900attempts;new SQLoptimization |15;round2-T4 reports | Coding |L0 | Current-source900+mixed after profiling | Local mock authorized |$0external |900s50 occupancy/SLO/noerrors | Stopfailedcohort;do not raise pool/timeouts |
| P3-I08 | IN_PROGRESS | Full50fault/fanout/restart absent | Crash/late/unknown/cancel regressions |15;campaign tests | Coding |L0 | Owned processkill/restart test matrix | Local authorized |$0mock | No replay/refund/liability loss | Retain uncertain;build faults |
| P3-I09 | BLOCKED | Real provider prerequisites missing | ModelGET;campaign25offline |13;19 | OpenAI/Coding |staging projectunknown | Sections4/10 | Read+existing$3authority;no prodactivation |≤$3cumulative after gates | Quota/pricing/controller/quality verified | Stop+retain ledger;read Limits |
| P3-I10 | IN_PROGRESS | Model/Voyage socketreuse baseline | SDK shutdown/transporttests |15 | Coding |L0 | Measure50transportreuse/cancel/socketcleanup | Local authorized |$0mock | Finite sharedclients/no leaked sockets | Prior transportconfig;localTCPbench |
| P3-I11 | IN_PROGRESS | Polling still costly |9→6→4→3 savedpoll queries | test_scale_polling.py;15 | Coding |L0 | Safe waking/batching only with fresh auth | Code authorized |$0 | No stale revocation;checkoutSLO | Revert if stale;measure current profile |
| P3-I12 | DEFERRED | Extra topology unjustified | No new workers/Redis |05;12 | Coding |L0 | Revisit only after singleprocessgates | No cloudactivation | Unknown | Sharedstate/fencing designed | Keep oneAPI;finish baseline |
| P4-E01 | FAILED | Target-size sustainedload not run | Healthy m7i-flex/SSM snapshot;L0failed | round2-cloud.json;15 | EC2/Coding |target/L0 | Section8 resource/traffic/cost,approved targetload | Readnow;deploy/restart confirmation | ExistingEC2billing | NoOOM/pooltimeout/restarts | Prior compatibleimage;measure cgroups |
| P4-E02 | IN_PROGRESS | Active-turn drain/rollback untested | Linux37unit+signal smoke prior |15;deploy/compose.staging.yml | Coding/EC2 |L0/target | Isolated active-turn+workerfence then exact rollout | Code;cloudrestart confirmation | Singlehostdowntime | Holds retained;old worker fenced | Reviewed digest/env;run isolateddrill |
| P4-E03 | IN_PROGRESS | Alerts delivery/instrumentation partial | Content-free diagnostic/templates | section7;round2-cloud.json | AWS/Coding |…3536/L0 | Finish definitions then quote/approve alarms | Read/code;activation confirmation | Monitoringcharges | Metric+notification canary | Disable onlynewactions;read dimensions |
| P5-L01 | IN_PROGRESS | Full T1/T5/T7/T8 modes missing | Guarded runner+local probes | scale_readiness.py;15 | Coding |L0 | Growth/mixed/chaos/network/liveguard integration | Code authorized |$0mock | Exact ownedtarget/provenance/cleanup | Stoponfailure;implement missing modes |
| P5-L02 | BLOCKED | Release evidence incomplete | Branch implementation/tests/handoff |12–20 | GitHub/cloud |branch/fingerprints | Close G00–G15 with scoped evidence | No merge/deploy authorization | Perapprovedchange | No unresolved P0/P1 releasefacts | MaintainNO-GO;follow gates below |

Table evidence names refer to `docs/scale-readiness/evidence/` unless a source path
is given. Historical `.log` evidence is sanitized when published; raw pstats,
browser sessions, unapproved workspace artifacts and credentials are excluded.
Fresh execution results and exact commands are in15 and round2 summaries.

Local cleanup exception (P5-L01):Docker Desktop became unavailable after the
completed tests. Two UUID-owned disposable containers could not be inspected/removed;
temporary credentials were deleted. [Exact cleanup record](evidence/round2-cleanup.json)
contains both UUIDs and the guarded remove commands to run once the local daemon
is available. This requires a local coding environment, not Work's cloud browser;
no unrelated database/container should be removed. Do not claim cleanup complete.

## 12. Release gates G00–G15

| Gate | Current decision | Evidence required / executable next step |
|---|---|---|
| G00 | PARTIAL | Verify pushed SHA via GitHub; inspect candidate CI, immutable image digest and deployed provenance separately. A feature push is not deployed evidence. |
| G01 | PARTIAL | Sections1/3/4/6/8:complete account-specific compute/pooler/SMTP/Auth/OpenAI/billing facts. |
| G02 | BLOCKED | Section5 rotate active owner secret and section6 hosted DB+objects+vault+EBS restore rehearsal. |
| G03 | PARTIAL | Confirmed Auth1000 and90day dataset/query/privacy proof; existing1000 appusers synthetic only. |
| G04 | LOCAL_ADMISSION_ONLY | Approved real distributed100signup→delivery→confirm→login with timings, not just HTTPacceptance. |
| G05 | LOCAL_ADMISSION_ONLY | Same real100 lifecycle through oneNAT; retain negative abuse/CAPTCHA and verify egress policy. |
| G06 | FAILED/PARTIAL | Actual budgets plus current-source checkoutp95<100ms/no timeout under full mixedload. OneSQL improvement is not gatePASS. |
| G07 | PARTIAL | Parent/child pooled bound, every paid provider/scope, crash/retry/unknown proof and livecampaign binding. |
| G08 | FAILED | Current-source50parents+SSE900s full profile/SLO; ASGI evidence is separate from sockets. |
| G09 | NOT_RUN | Section4 facts+10safeadapter;≤$3 cumulative realprovider test/quality; scale down report scope if full profile cannot fit cap. |
| G10 | NOT_RUN_FULL | Full interactive+proactive/guest/journal/embedding/maps mixedprofile and financial fairness. |
| G11 | PARTIAL | Network disconnect/replay/revoke/slowreader/restart/cancel chaos, no private output after fences. |
| G12 | FAILED/UNKNOWN | TargetEC2 sustainedmetrics,900sreal+2hmock as required; Flex CPU/economics and noOOM/restart. |
| G13 | PARTIAL | Section7 numeric instrumentation, installed approved alarms and delivered/recovered canary. |
| G14 | PARTIAL | Approved active-turn/worker-fence/drain/network/compatible-rollback rehearsal; unit/signal plumbing insufficient. |
| G15 | OPEN | Close P0/P1, review actual evidence and obtain exact release SHA/digest/window approval. No merge/main/deploy in this task. |

Record each browser action with UTC timestamp, account/project fingerprint, exact
navigation/API and redacted result, not just a checkbox. If denied/login/MFA blocks
one site, document it and continue independent authorized work. Never mark an
operation complete without reading back its resulting state.

GitHub CI follow-up (G00):the first implementation push failed20Ruff import-order
checks, corrected in a subsequent CI correction commit. Exact fullCI Ruff and full `mypy app` (194files) now pass
locally;118offline tests pass/2skip after import normalization, then74pass/1skip
after2static typing clarifications. Counts overlap;no runtimepolicy changes. Verify the final revision's
Actions run rather than assuming the earlier failure or a local lane proves its
status. [Original failed run](https://github.com/mhiu05/MoodPrint/actions/runs/42027966645),
[normalization evidence](evidence/round2-ci-import-fix.json). Fullworkflow status may
still be pending;it is not a release authorization.


## Continuation handoff — 2026-11-05T15:35:36.210Z

### Branch, CI and scope

- The original pinned implementation `ed75c4a1fbef462f33ad5389e0615b9afaa4b6da` remains in branch ancestry. Three test-only corrections are present at code tip `fdb5dc9897562b0d8550058218f7579411b1c2c5`: commits `d655ee86`, `48a1df2f` and `fdb5dc98`. No runtime source behavior changed in those commits.
- Documents 12–15 were updated on this authorized branch through direct GitHub edits; the 41 original task IDs were left intact. The pre-handoff-update branch tip was `7e6a7ba71893d9b34fbe0bc9614e0f011a1df825`; this document commit will advance it.
- At capture time, code run [#365](https://github.com/mhiu05/MoodPrint/actions/runs/42051313537) and documentation runs [#366](https://github.com/mhiu05/MoodPrint/actions/runs/42055163060), [#367](https://github.com/mhiu05/MoodPrint/actions/runs/42055762077), [#368](https://github.com/mhiu05/MoodPrint/actions/runs/42056032936) and [#369](https://github.com/mhiu05/MoodPrint/actions/runs/42056338281) were IN_PROGRESS. Runs #363/#364 failed in backend checks; #362 is the reported 2,276-pass/3-fail/4-skip baseline. Read the newest run after this commit before reporting CI completion.
- No merge, main-branch update, deployment, database migration or local test execution occurred. CI status is still unknown for the fixes.

### Cloud facts to carry forward

- AWS account ending 3536, `ap-southeast-2`: target EC2 `i-0664d6ea5930452db` is running as `m7i-flex.large`, health checks passed. CloudWatch has EC2 metric series but no alarms; no numeric sample was captured. Billing is denied. EBS snapshots, AWS Backup plans/protected resources/recovery points, and SNS topics are all zero.
- SES is sandboxed at 200 recipients/day and 1/s; one Gmail sender identity is verified, no dedicated sending domain exists, and no production request was submitted. The paste-ready transactional request and quota proposal (5/s, 3,000/day) are in document 14.
- Supabase target is project ref `roznanxbiyqybjpvtilq`, fingerprint `44a655e04517`, Pro/Tokyo/PostgreSQL 17.11. Despite the UI label `VDaAgent`, the fingerprint matches MoodPrint. Current Migrations view showed `0020_private_profile_retirement` only, inconsistent with the expected `0029_journal_intelligence`; do not apply a migration until reconciled.
- Supabase compute/pooler: Micro/1 GB shared; pool size 15; max client connections 200. Daily DB backups were visible, latest observed at 2026-11-05 02:23:02 UTC; Storage object bytes are not covered, PITR is off, and `journal-media` is private. No DB/Auth/SMTP setting was changed. Auth currently has confirmation and Turnstile enabled, Auth IP forwarding off, and Leaked Password Protection off; personal Gmail SMTP is configured and its email-send-rate value was redacted.
- OpenAI Platform exposed only Personal Organization → Default project, not a MoodPrint staging project. Model catalog visibility does not establish `gpt-6-luna` project access or RPM/TPM. No model call was made; the approved $3 cumulative staging budget was not spent.

### Owner action and secure handoff

- Rotation proposal is only for the active `postgres` migration-owner password in the fingerprint-matched Supabase project: Database → Settings → Database password → Reset password. Dashboard warns that resetting breaks existing connections. The owner must enter, confirm and submit the replacement directly into the dashboard and store it in their password manager. Approval is still required before opening that reset flow. Do not change `moodprint_backend` or its runtime SSM secret.
- After an approved reset, update only inventoried migration/admin DSNs, verify new TLS login and old-password rejection, and check runtime role and readiness. Treat a network timeout as UNKNOWN, not rejection. Do not restart or terminate active app connections.
- SES production access remains unsubmitted pending owner approval; SMTP activation, sender/DNS changes, Auth security/rate-limit changes, paid backups, EBS snapshots, CloudWatch alarms/SNS subscriptions and hosted restore also require specific approval. Billing access and data sizes must be resolved before cost approval.
- Correct OpenAI staging project identification is still needed. Once confirmed, verify model access and project quotas without generating a paid response. The previously approved $3 staging campaign remains constrained to `gpt-6-luna`; no judge-model calls.

### Release decision

G00 remains PARTIAL; G01 PARTIAL; G02 BLOCKED; G03 PARTIAL; G04/G05 LOCAL_ADMISSION_ONLY; G06 FAILED/PARTIAL; G07 PARTIAL; G08 FAILED; G09 NOT_RUN; G10 NOT_RUN_FULL; G11 PARTIAL; G12 FAILED/UNKNOWN; G13 PARTIAL; G14 PARTIAL; G15 OPEN. Full descriptions remain in the updated document 15. Release remains **NO-GO** until evidence and the exact release approval close the gates.
