# Owner actions và activation approvals

## Current authority and exact proposals — supersedes earlier prerequisites

Local engineering/read-only inspection and normal feature-branch push are approved.
RPO/RTO technical selection delegated and completed:RPO24h/RTO8h planning targets,
not achieved. Keep DuckDNS app URL; no custom-domain purchase required for coding.
Named conditional EC2 Start approved; resource already running m7i-flex.large, no
Start issued. Do not repeat approval requests for50registered AI turns/$50day target,
$3 cumulative staging campaign/Luna-only/no judge API. Production activation is separate.

| Change | Exact proposed action / preparation | Status / impact / rollback |
|---|---|---|
| C01 security | Reset ONLY active postgres owner password on matching Supabase project, after independent admin/MFA recovery and external-consumer inventory;update migration consumers;verify newTLSlogin/oldreject/runtimehealthy. SSM runtime uses a different password and has no migrationURL. Full ordered procedure in20. | **REQUIRES_OWNER_CONFIRMATION**. Admin/migration interruption possible; do not change runtime secret or restart blindly. Recover via another NEWsecret, never exposedpassword. |
| C02a identity | Earlier singleGmail identity verification; latest owner also authorizes carefully controlled tests using this existing verified identity within SES restrictions | Identity approved/executed/verified. Controlled existing-identity tests authorized; productionSMTP/newidentity/DNS/domain actions still require their own confirmation. |
| C02b SES | Read dashboard;prepare transactional request using actual DuckDNS URL and disclose sender/alignment limits;propose numeric quotas≥5/s,3000/day for review. | **REQUIRES_OWNER_CONFIRMATION** before submit/quota/configset/eventdestination. Sendingcharges afteractivation;retain suppression. |
| C02c sender/SMTP/Auth | Inspect existingGmail/DMARC/headers and hostedSMTP/rates/CAPTCHA first;present exact sender/SMTP/limits/forwarding diff. Domain is a fallback if alignment/reliability cannot be satisfied, not a blanket prerequisite. | **REQUIRES_OWNER_CONFIRMATION** for productionSMTP/DNS/newidentity/domainpurchase/Authpolicy. Cost quote and priorvaultconfig rollback needed. Never disableconfirmation. |
| C03 NAT deployment | Candidatepolicy remainsoff;review image/digest+effectiveAuthfacts+canarymanifest before realcohort/deploy. | Not ready foractivation. **REQUIRES_OWNER_CONFIRMATION** for hostedpolicy/deploy/accountcohort;retain existing abuseguards. |
| C04 AI activation | Complete pooled/all-provider/campaignadapter/quality/load gates,then propose reviewed50/$50runtime diff. | Not ready. **REQUIRES_OWNER_CONFIRMATION** for productionbudget/flags/projectlimits/deploy;stopadmission andretainholds onrollback. |
| C05 staging/deploy | Targetalready runninghealthy. Read traffic/billing/cgroups;prepare isolatedactive-turn/drain/workerfence/rollback and exact reviewed rollout. | No furtherresize proposed. **REQUIRES_OWNER_CONFIRMATION** for restart/productionmigration/deploy/paidupgrade;previouscompatibleimage+env,neverautomaticDBdowngrade. |
| C06 backup/monitoring | Policyselected;quote encrypted12hindependentDB/object/config/vaultcopies,7dailyEBSversions and isolatedrestore;read metricdimensions and quote alarms/channel/retention. | **REQUIRES_OWNER_CONFIRMATION** before paid/cloudactivation,hostedrestore,notifications. Neverrestoreintoproduction/deletebackups;noRPO/RTOclaimbeforehostedtest. |

[16](16-work-handoff.md) has exact navigation,targets,success criteria,next executable
actions and permissions;[18](18-recovery-runbook.md) recovery,[19](19-paid-campaign-runbook.md)
campaign,[20](20-security-cloud-actions.md) credential transition. These are concrete
preparations; no production/cloud action is marked completed without evidence.

## Earlier proposal history

D03,D05,D10,D12 và target$50/day đã được chấp thuận; không yêu cầu quyết định lại.
Ngoại trừ **C02a đã được owner duyệt và xác minh thành công**, các action dưới đây chưa thực thi. Chưa đủ prerequisite thì trạng thái
`NOT_READY_FOR_APPROVAL`; tài liệu không phải permission hay lệnh deploy.

## C01 — Credential đã lộ:rotation có phối hợp

- Target:credential database trong local `backend/runtime.txt`; chỉ phát hiện category, không xuất value.
- Current:previous audit đã in credential; chưa có evidence credential cũ bị thu hồi. Production security blocker.
- Proposed:xác định vault/SSM consumers và role, backup config ngoài repo, tạo transition được review,
  cập nhật đúng runtime/migration consumer, reconnect canary, verify credential cũ hết hiệu lực.
- Benefit:rút ngắn thời gian credential có thể bị lạm dụng. Risk:auth/DB outage nếu thiếu consumer.
- Cost:không tăng infrastructure dự kiến; downtime tùy quy trình và connection drain, chưa cam kết0.
- Prerequisites:owner xác nhận credential scope/live status, administrative recovery path và maintenance window.
- Execution:owner/agent thực hiện từng mutation sau approval cho exact role/resource; không đưa password vào command/chat/evidence.
- Verify:runtime health/session/AI canary được duyệt, role privileges giữ nguyên, old credential denied.
- Rollback:vault transition được review; không tự khôi phục credential đã bị compromise.
- Approval:**PENDING,NOT_READY_FOR_APPROVAL** cho đến khi có exact credential scope/consumers.

## C02 — SES production access + verified sender + SMTP

- Target:account…3536,ap-southeast-2;SES Essentials sandbox200/day,1/s,0 verified identities/config sets.
- Proposed:owner chọn domain/From;verify identity/DKIM/MAIL FROM và DNS;production access;
  candidate quota≥5recipient/s,≥3000/day;Supabase custom SMTP/confirmation/rates phải đồng bộ.
- Benefit:hỗ trợ100 signup/60s và email confirmation. Risk:DNS/SMTP sai khóa onboarding, abuse/email cost tăng.
- Cost:SES usage/DNS/eventing theo giá account/region;chưa có quote đáng tin. Không tự tạo SNS/SQS hay service mới.
- Downtime:dự kiến không cần restart API cho hosted SMTP, nhưng email có thể gián đoạn nếu credentials sai.
- Backup:chụp configuration metadata không có secrets;secret cũ giữ trong vault theo transition policy.
- Steps:read baseline DNS/SMTP→owner approve exact records/settings→verify identity/DNS→request production access/quota→
  nhập SMTP credential trong Supabase secure UI→controlled mailbox canary→100-user staging sau approval riêng.
- Verify:accepted/created/SES-accepted/delivered/confirmed/login được đo riêng;bounce/complaint/suppression hoạt động.
- Rollback:previous SMTP/redirect/rate config từ vault snapshot;dừng test arrivals;không xóa suppression hay identities hàng loạt.
- Approval:**NOT_READY_FOR_APPROVAL**:domain/From và hosted SMTP baseline còn thiếu;đã hỏi owner thông tin này.

Owner xác nhận Gmail chỉ dùng cho canary; domain production sẽ chọn sau. Quyết định này
không yêu cầu hỏi lại. Chưa tạo SES identity hoặc gửi thư xác minh. Canary cần approval
cho thao tác cụ thể và recipient đã xác minh trong SES sandbox. Production sender/DNS/SMTP
vẫn BLOCKED cho đến khi có domain do owner quản lý và cấu hình được review.

### C02a — Canary email identity, tách khỏi production SMTP

- Target: SES account …3536, ap-southeast-2, đúng địa chỉ Gmail owner đã chọn trong hội thoại.
- Current: sandbox, 0 verified identities. Owner đã chọn Gmail chỉ cho canary.
- Exact action: gọi `sesv2.CreateEmailIdentity(EmailIdentity=<Gmail đã chọn>)` một lần;
  AWS gửi thư xác minh tới mailbox đó. Owner đã duyệt các bước xác minh;
  agent hoàn tất qua đúng mailbox Gmail đã kết nối.
- Benefit: có sender/recipient thử nghiệm được xác minh cho canary sandbox.
- Security/user impact: thêm đúng một email identity; không ghi SMTP/API credentials vào repo.
  Gmail không cho quyền cấu hình DNS/DKIM của gmail.com; không đóng production delivery gate.
- Cost: không provision compute/domain/event services; chưa có account-specific quote cho
  canary gửi thực tế, nên thao tác này chỉ gồm identity và verification email.
- Downtime: không đổi runtime/SMTP hoặc sender đang dùng, không cần restart.
- Verify: read-only `GetEmailIdentity` phải trả verification SUCCESS sau khi owner mở link.
- Rollback: xóa đúng identity mới nếu owner yêu cầu và đã xác nhận không có consumer;
  không xóa identity khác hay suppression entries.
- Approval: **APPROVED/EXECUTED/VERIFIED** cho identity + một verification email. Real confirmation/recovery
  canary và production SMTP vẫn là các hành động có scope/approval riêng.

**Executed, 05-11-2026:** owner duyệt tạo identity và các bước xác minh. Một email identity
đã được tạo; thư AWS được đọc từ đúng mailbox đã chọn và link xác minh được dùng đúng
destination AWS. `GetEmailIdentity`: **SUCCESS**, `VerifiedForSendingStatus=true`.
Không lưu link/token trong evidence; không replay link khi HTTP client báo lỗi response,
vì SES đã xác nhận trạng thái thành công. [Evidence](evidence/ses-canary-identity.json).
Approval C02a đã hoàn tất; không hỏi lại. SES sandbox/quota và production SMTP không thay đổi.

## C03 — Candidate code/image và Auth NAT policy

- Target:reviewed candidate SHA/digest chưa được publish;SSM v26 AUTH_CAPTCHA_ENABLED=true.
- Proposed:`AUTH_NAT_POLICY_ENABLED=true` sau negative/staging tests:
 150attempt/action/60s cho signup/confirmation/recovery/login/reset,aggregate600/IP/900s;
 email3/action/hour và login10/email/900s giữ;CAPTCHA bắt buộc;origin/trusted proxy giữ.
- Benefit:100 legitimate cùng NAT không bị shared40/900 bucket chặn ngay tại app.
- Risk:expanded IP admission có thể tăng abuse traffic;provider quota và CAPTCHA vẫn là prerequisites.
- Cost:không thêm fixed service;provider/email traffic có thể tăng.Downtime:controlled image recreate,không cam kếtHA.
- Steps:review exact diff+digest→staging fake/real controlled auth→snapshot deployment/env→drain/worker fence→
  deploy reviewed image/config→verify signup/confirm/login/negative cases→owner mở traffic.
- Verify:100 legitimate cohort và email timeline;missing/invalid CAPTCHA,email cooldown,brute force,spoofed headers vẫn denied.
- Rollback:flagfalse dùng shared legacy40/900;previous compatible image/env;không rollback user data.
- Approval:**PENDING**,không kích hoạt trước khi hosted quotas/trust chain/email gates đóng.

## C04 — Global AI$50 + bounded reservation/dispatch activation

- Target:SSM `/moodprint/staging/runtime` v26 hiện budget20/global10;không chứng minh deployed container.
- Proposed review group:budget50,global parent50,accountingtrue;candidate bounded64k/1200/3calls,row hold$0.12;
  API50/proactive2 physical slots (52 total),queue100,one API/one worker;guest budget/allocation giữ nguyên.
- UX:không cắt context;ngữ cảnh>64k bị từ chối rõ ràng.Native hosted tools/stateful/file input chưa hỗ trợ trong bounded path;
  exact-count preflight trước mỗi generation thêm latency/network.Đây là tradeoff cần approve sau quality canary.
- Financial:atomic lock/versioned holds,unknown giữ liability;legacy$2 fallback còn.Candidate generation bound không đồng nghĩa
  đã chốt hard cap cho mọi Voyage/STT operation hoặc count-endpoint fees;đây còn là engineering/release blocker.
- Prerequisites:actual model/project RPM/TPM/price+count endpoint,all-provider accounting scope,50/fanout/fault tests,
  quality review và resource budget;không tăng tiền để che lỗireservation.
- Cost:hard target50/day toàn app,không yêu cầu chi50/day.T5 tối đa3USD toàn campaign,chỉLuna,no judge API.
- Steps:review flags/pricing/contract→staging mock→small bounded Luna canary nếu đủ prerequisites→offline judge→
  approve exact image+SSM version diff→drain→activate→verify admission/ledger/uncertain carryover.
- Rollback:ngừng admission mới,tắt bounded/dispatch flags,restore reviewed global10/budget20 nếu đủ liability;
  giữ mọi v1/v2 open/uncertain holds,không xóa ledger hoặc refund unknown để rollback.
- Approval:**NOT_READY_FOR_APPROVAL**;chưa đề nghị bật production khi các điều kiện tài chính còn mở.

## C05 — Database/process/resource policy và deploy

- Target:DB role limit20,max_connections60;pooler caps UNKNOWN;EC2 đangt3.small,targett3.large chưa test.
- Proposed:giữ API4+1/proactive2+0/maps1+0 chỉ sau effective-config/role/pooler/server gate;
  SET LOCAL statement15s/lock2s candidateflagfalse;container grace270s/server grace theo2×turn timeout+cleanup.
- Resource resize:none approved/recommended yet;đo target-size staging trước sizing,cost/credit/host RAM phải có evidence.
- Benefit:bounded waits và drain có contract.Risk:timeouts quá thấp,false rejection,planned downtime.
- Cost:local code không thêm recurring service;CloudWatch/resize/PITR cần quote/approval riêng.
- Backup:DB+Storage/EBS recovery prerequisites;RPO/RTO/maintenance window còn cần owner chốt.
- Steps:read effective Compose+capacity facts→review calculated demand→approved staging rehearsal→
  SIGUSR1 drain (new image only),ready503,new message503,read/cancel giữ→worker fence→controlled recreate→health/SSE→rollback drill.
- Verify:no lost financial holds,no replay,no pool timeout,50 workload resource data,alarm canary delivery.
- Rollback:previous compatible digest/env/pool/timeouts;retain worker fencing;không downgrade schema tự động.
- Approval:**NOT_READY_FOR_APPROVAL**;không resize,ALTER role,push migration,restart hoặc deploy trong phiên.

## C06 — Observability/backup và policy còn thiếu

Chỉ apply reviewed alarm/dashboard sau owner chốt notification channel/retention/cost budget.
Không gửi tin nhắn hoặc tạo billable monitoring tự động.Backup/PITR/Storage restore cần isolated target và cost approval cụ thể.
Session purge TTL,RPO/RTO và maintenance/SPOF acceptance chưa có quyết định đầy đủ;giữ conservative behavior hiện tại.
Các công việc code chưa xong được ghi trong [12](12-implementation-progress.md);không chuyển engineering gaps thành owner approvals.


## Owner decision refresh — 2026-11-05T15:31:58.534Z

The following are precise proposals from the attached-Chrome review. None was submitted or applied.

### C01 — Approve rotation of the exposed migration-owner credential

- Target: Supabase project ref `roznanxbiyqybjpvtilq`, verified fingerprint `44a655e04517`; reset only the `postgres` database-owner password.
- UI action: Database → Settings → Database password → **Reset password**. The dashboard states the current password cannot be viewed and the reset breaks existing connections.
- Approval covers opening the reset flow and handing the page to the owner. The owner must create/store the replacement in their password manager and personally enter, confirm and submit it. Do not put the password in chat, logs, command-line arguments or repository files.
- Before reset: confirm admin/MFA recovery, inventory migration/admin consumers, and pause only migration/admin work. After reset: update only the migration-owner DSNs, verify new TLS login and old-password rejection, then verify the separate `moodprint_backend` role and app health. Do not change that runtime password, its SSM value, or restart the service.
- Current status: **REQUIRES_OWNER_CONFIRMATION**; old credential was still active at last verification. No reset was attempted.

### C02 — SES transactional production-access request draft (not submitted)

> MoodPrint is a user-facing web application at https://moodprint.duckdns.org. We are requesting Amazon SES production access in ap-southeast-2 for strictly transactional email initiated by a user: signup address confirmation, password recovery and account-security notices. Users provide their own address in the signup or recovery flow; we do not send marketing, purchased lists, unsolicited messages or third-party bulk mail. Our planned cohort is up to 1,000 registered users, with bursts of about 100 signup attempts, so we request an initial quota of 5 messages/second and 3,000 messages/24 hours to provide confirmation and recovery headroom. Our verified sender is one Gmail email identity; we do not own a dedicated sending domain and are not claiming domain-level DKIM, custom MAIL FROM or DMARC alignment. Before expanding sending, we will verify bounce/complaint suppression, transient-only retries, reputation monitoring and a pause procedure. Please assess production access and these initial quotas; we understand sender alignment may limit delivery reliability.

- Current status: **REQUIRES_OWNER_CONFIRMATION** before submission or quota request. The account is sandboxed at 200 recipients/day and 1/s. The Gmail sender is verified; no dedicated domain was invented or purchased.
- The request describes planned capacity, not observed current traffic or a guarantee of SES approval. Production access would not by itself authorize turning on production SMTP.

### C02c — Supabase Auth/email exact diff to review after SES decision

- Keep email confirmation enabled, Turnstile CAPTCHA enabled, current site/redirect allowlist, and existing abuse protections.
- Proposed security change for owner review: Leaked Password Protection **disabled → enabled**, after checking the app's recovery and signup UX. No setting has been changed.
- Keep Auth IP forwarding off until the trusted proxy path and forwarded-header behavior are verified. Do not copy a client-supplied forwarding header into Auth trust configuration.
- Custom SMTP currently uses a personal Gmail provider. Propose moving to SES only after production access, sender identity and a verified delivery canary are approved. The Supabase email send-rate value was redacted in the browser; obtain it through a safe dashboard view before proposing a numeric SMTP/Auth rate diff.
- Any SMTP, sender, DNS, Auth or rate-limit update remains **REQUIRES_OWNER_CONFIRMATION**.

### C06 — Backups, monitoring and restore

- Observed: Supabase daily database backups exist, but exclude Storage object bytes; PITR is off. AWS has no EBS snapshots, AWS Backup plans/protected resources/recovery points, CloudWatch alarms or SNS topics.
- Proposed target policy remains RPO ≤24h / RTO ≤8h, not achieved. Price encrypted off-project database and private `journal-media` object copies, daily encrypted EBS snapshots with a seven-day window, and a secure configuration/secrets recovery set; then rehearse to isolated resources and measure actual RPO/RTO.
- No reliable cost estimate is available because the AWS Billing view is denied and current object/EBS sizes were not captured. Do not create billable copies, snapshots, alarms, SNS subscriptions or restore resources until the target sizes, monthly estimate, notification recipient and rollback are reviewed.
- Current status: **REQUIRES_OWNER_CONFIRMATION** for all billable cloud changes and hosted restore.

### C07 — Identify OpenAI staging project

- The connected Platform session exposed only Personal Organization → Default project; no MoodPrint staging project could be identified. The visible `gpt-6-luna` catalog entry does not prove access or project limits.
- No model call was made. The approved $3 cumulative staging campaign remains authorized but cannot begin until the correct project, model access, RPM/TPM and safe campaign adapter are verified. Production $50/day activation remains a separate **REQUIRES_OWNER_CONFIRMATION** decision.
