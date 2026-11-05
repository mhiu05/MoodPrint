# Cloud inventory — read-only, redacted

## Current verified snapshot — 2026-11-05, 17:54–18:00 Asia/Bangkok

This section supersedes earlier t3.small/SSM-only observations below.
[Sanitized API/SSM evidence](evidence/round2-cloud.json), [security/consumers](20-security-cloud-actions.md),
[sender facts](evidence/round2-sender-policy.json). Cloud configuration was not changed.

| Field | Verified now | Still unknown / limit |
|---|---|---|
| Account/region/identity | AWS…3536/ap-southeast-2; i-0664d6ea5930452db; Name moodprint-staging; Application MoodPrint; Environment staging | Account-wide traffic/environment inventory not implied |
| State/type | **running m7i-flex.large**,2vCPU/8192MiB SKU; status instance/system/EBS allok | No Start needed/issued; no target-size sustainedload |
| AMI/volume | Ubuntu24.04 x86_64 HVM/ENA compatible; root30GiB encrypted gp3 in-use/attached,3000IOPS/125MiB/s | Latest exact target-volume snapshot query0; other backup systems unknown |
| EIP/DNS/TLS | Same EIP13.210.93.93 allocationeipalloc-0c23e4fdcdce12bc9; DuckDNS points there; TLS1.3 verified,certificate expires2027-01-23; / and ready200 | Genuine public-user/production traffic volume unknown |
| Connectivity | SSM Online **and Run Command Success/response0** | TCP22 timeout; authenticated SSH untested |
| Services | web/api/proactive/maps running and healthy,restart0 snapshot | Historical restart/OOM/throttle/error distributions unknown; no restart rehearsal |
| Host resources | ~7.59GiB usable,6.62GiB available,no swap,load.15/.12/.05 | Idle snapshot, not 50-user metrics |
| Effective deployed config | API4+1,proactive2+0,maps1+0; AIglobal10,user2,timeout60s,budget$20,accountingtrue; CAPTCHAtrue | Candidate50/$50 not activated; image manifest/releaseSHA not verified |
| Economics | Price List API:Linux/shared On-Demand Sydney **$0.1197/hour**,effective2026-11-01; nonburstable/Flex rather than T3credits | ~US$87.38/730h compute only,plus EBS/IPv4/network/tax; actual discounts/free-tier/account credits unknown; Flexbaseline40% is not guaranteed sustainedfullCPU |
| SES | Sandbox,healthy,sendingtrue,200recipients/24h,1/s,sentlast24h1; one EMAIL_ADDRESS verifiedSUCCESS | No SMTP/realAuthmail canary; no production-access request submitted |
| Sender | Existing Gmail identity can support controlled allowed tests; public GmailDMARCp=none,subdomainp=quarantine at lookup | DMARCalignment/reputation/providerpolicy/deliverability unproven; verification is not reliablepublicmail proof |
| Exposed DB secret | Active postgres migration owner/TLS,CREATEROLE/DB+BYPASSRLS; distinct runtimepassword | Not rotated; external consumers/history incident scope incomplete |
| Supabase/OpenAI | Prior projectPro/Tokyo/role20/server60 and modelmetadata200 remain latest verified scoped facts | Actualcompute/pooler/backups/SMTP/Authlimits and OpenAIprojectRPM/TPM/accountprice/countfees stillunknown |

Public price evidence:[round2-ec2-pricing.json](evidence/round2-ec2-pricing.json).
Account billing values must be read from current account data before a consequential
cost decision. Starting permission does not authorize a deployment, further resize
or budget change. See [16](16-work-handoff.md) for secure browser/account mapping.

## Earlier inventory history

Ngày quan sát:2026-11-05, timezone hiển thị Asia/Bangkok; timestamps chi tiết trong JSON là UTC.
Inventory là read-only; ngoại lệ duy nhất là C02a SES canary identity được owner duyệt riêng
và xác minh thành công sau inventory. Không đổi role, SMTP, DNS, IAM, budget hoặc instance.
Không xuất credential values.

## AWS: account …3536, ap-southeast-2

Nguồn:[AWS API evidence](evidence/aws-inventory.json), qua AWS MCP `call_boto3`;
STS xác minh account trước các Describe/Get. `DescribeRegions` tại ap-southeast-1 bị SCP deny;
region đích ap-southeast-2 lấy từ deployment config rồi xác minh bằng resource tags.
Chỉ tìm resource `Application=MoodPrint`; không suy ra không có resource ở region khác.

| Field | VERIFIED | Capacity implication |
|---|---|---|
| EC2 name/environment | moodprint-staging, running | Không phải production proof |
| Instance type | **t3.small**,2 vCPU; t3.large vẫn là target | Chưa đo target2 vCPU/8GiB; không resize tự động |
| Credit mode | unlimited | Có thể phát sinh surplus nếu sustained; snapshot hiện surplus0 |
| 24h CPU |288 samples, max39.878%, latest average7.870% | Existing workload; không phải50-user load |
| Credit balance | latest576; surplus balance/charged0 | Không chứng minh24h economics sau scale |
| EBS |30GiB gp3, encrypted,3000IOPS,125MiB/s | Growth/restore chưa rehearsal |
| SSM/IAM/IMDS | SSM Online Ubuntu, profile attached, IMDSv2 required | Không chứng minh least-privilege policy hoặc deployed digest |
| Alarms |0 alarms có prefixMoodPrint | Không chứng minh account không có alarm tên khác |
| Snapshot |0 snapshot của volume đích trong query | AWS Backup/retention khác UNKNOWN; không có restore evidence |
| SES plan | ESSENTIALS | Plan không đồng nghĩa production access |
| SES access | **ProductionAccessEnabled=false**,SendingEnabled=true,HEALTHY | Sandbox chặn campaign tới recipient chưa verified |
| SES quotas |200 recipient/24h,1/s,SentLast24Hours=0 | Không đủ admission email100/60s có headroom |
| SES identities/config sets |0/0 trong region này | Sender/DKIM/MAIL FROM/event delivery chưa sẵn sàng |
| Suppression | BOUNCE,COMPLAINT | Giữ nguyên, không xóa list |

Nguồn:[SSM allowlist evidence](evidence/ssm-inventory.json), parameter `/moodprint/staging/runtime`,
version26,14:20:17 Asia/Bangkok. Chỉ trả numeric/boolean allowlist và duplicate key names/lines;
không trả nội dung SecureString. **SSM configuration khác deployed container configuration.**

| Setting | SSM value |
|---|---:|
| AI_GLOBAL_CONCURRENCY / AI_USER_CONCURRENCY |10 /2|
| AI_TIMEOUT_SECONDS |60|
| AI_DAILY_BUDGET_USD |**20, chưa kích hoạt50**|
| AI_ACCOUNTING_ENABLED |true|
| DATABASE_POOL_SIZE / OVERFLOW / TIMEOUT |5 /2 /10|
| AUTH_CAPTCHA_ENABLED |true (backend expectation)|
| PROACTIVE_WORKER_ENABLED |true|

Không có key allowlist trùng trong SSM. Compose có thể override pool4+1; không lấy5+2 từSSM làm effective API pool.
Deployed SHA/digest, effective container env, RSS/cgroup/throttle, memory host, CloudWatch agent delivery:UNKNOWN.

## Supabase: configured project fingerprint44a655e04517

Nguồn:[read-only SQL](evidence/supabase-readonly.json),13:29:40 Asia/Bangkok;
endpoint lấy từ local config, credential không xuất ra artifact. Chỉ SELECT catalog/aggregate metadata.
Chưa có dashboard xác nhận mapping project/plan với deployment, nên không nâng thành production verification.

| Field | Observation |
|---|---|
| PostgreSQL |17.11|
| max_connections |60|
| Runtime role connection limit |20|
| Runtime role flags |superuser=false,BYPASSRLS=false|
| DB size lúc đọc |18,192,051 bytes|
| Migration head |0029_journal_intelligence|
| Existing connection states |active1,idle7,idle-in-transaction4,other/not-visible6; snapshot, không phải peak|
| Role statement/lock timeout qua endpoint |2min /0; cần SET LOCAL benchmark, không ALTER role |
| Private RLS |Table-level flags trong JSON; không thay thế grants/schema-exposure/cross-user tests |

Nguồn:[Auth public settings](evidence/provider-readonly.json),13:36:33 Asia/Bangkok:
email provider enabled,disable_signup=false,**mailer_autoconfirm=false** (confirmation bật),anonymous_users=true.
Auth public endpoint không cho biết custom SMTP, quota, CAPTCHA provider/site origins hay IP forwarding.

Plan Pro và region Tokyo đã được xác nhận thêm qua MCP ở phần bổ sung bên dưới.
Compute SKU,pooler client/backend limits,toàn bộ Data API exposure/grants/Storage policy,
SMTP,Auth rate limits,backup/PITR/restore: **UNKNOWN**. Storage aggregate và mẫu private grants
được ghi riêng,không thay thế full policy audit.
Connection budget candidate:steady8+reserve4=12;all-overlap16+reserve4=20.
Role20 vừa đủ nhưng chưa chứng minh pooler/server còn đủ headroom. Không tăng pool/role.

## OpenAI

GET `/v1/models/gpt-6-luna` bằng configured project key trả200 và đúng model ID
([evidence](evidence/provider-readonly.json)). Không tạo response; không dùng generation để đo quota.
Official model/token-count guidance đã đọc; không thay model.

Project/org RPM,TPM,usage/spend,processing tier,account pricing,count-endpoint availability/pricing: **UNKNOWN**.
Public model/pricing không thay cho quota/project access. Paid canary chưa chạy.

Campaign:0 generation calls,$0 external generation spend,$3 remaining;0 judge API calls.
Coding-agent usage không được tính vào campaign ledger; không khẳng định chi phí coding agent bằng0.

## Access gaps

Browser automation riêng gặp sign-in; Chrome extension thấy phiên người dùng nhưng mở tab mới lỗi.
Đã yêu cầu owner mở Supabase/OpenAI Limits để đọc tiếp, không yêu cầu gửi password/key.
Cloud mutation vẫn cần approval riêng theo [14](14-owner-decisions-required.md).

## Bổ sung qua Supabase MCP,15:12 Asia/Bangkok

`list_projects/get_project/get_organization` xác nhận project khớp fingerprint44a655e04517,
statusACTIVE_HEALTHY,region **ap-northeast-1(Tokyo)**,org plan **Pro**. EC2 Sydney khác region;
chưa đoRTT từ runtime,không tự chuyển region/resize. ComputeSKU/pooler limits vẫnUNKNOWN.
Security advisor báo **leaked password protection disabled**; không tự bật policy hosted.
Performance advisor:Auth dùng absolute maximum10 DB connections;11 foreign keys thiếu covering index,
20 indexes chưa có usage. Đây là lint/info,không tự thêm/xóaindex nếu thiếuEXPLAIN workload.
Catalog helper:is_provider_session_active làSECURITY DEFINER,search_path rỗng,EXECUTE của
PUBLIC/anon/authenticated đềufalse. Role runtime20,max_connections60,migration0029 khớp read-only SQL trước.

Sender owner chọn là địa chỉ Gmail cá nhân (giữ mapping trong cuộc hội thoại,không ghi email vào metrics).
SES email-identity verification khả thi nhưng không có quyềnDNS củagmail.com để domain-alignDKIM/SPF;
khuyến nghị domain quản lý riêng cho transactional production. Chưa gửi verification email/chưa tạo identity.

Owner xác nhận **Gmail chỉ cho canary; chọn domain production sau**, rồi duyệt riêng C02a
cho tạo identity/gửi thư xác minh và các bước xác minh. Trạng thái mới nhất:
**1 canary EMAIL_ADDRESS identity verified SUCCESS**, sending verification true.
[Evidence sau mutation được duyệt](evidence/ses-canary-identity.json). Các dòng 0 identity
ở trên là snapshot trước C02a; sandbox/quota/SMTP/DNS/IAM giữ nguyên.

Nguồn bổ sung: [storage/grants catalog](evidence/supabase-storage-grants.json).
Bucket journal-media private, giới hạn 50MiB/file, có allowlist MIME; 6 objects với tổng
metadata size 9,473,860 bytes. Không đọc object names hoặc nội dung. Năm bảng private được
sample (users, auth_sessions, journal_entries, ai_messages, memories) có RLS bật và không
cho anon/authenticated SELECT. Đây là mẫu catalog, không thay thế toàn bộ policy audit.
shared_buffers=256MiB, effective_cache_size=768MiB là PostgreSQL settings, không phải bằng
chứng compute SKU. lock_timeout/idle_in_transaction_session_timeout=0 ở scope đã đọc.


## Attached-Chrome verification — 2026-11-05T15:30:19.555Z

All checks below were read-only in the owner's connected Chrome session. No project, Auth, email, database, billing, backup, or monitoring settings were changed.

### AWS, account ending 3536, ap-southeast-2

- EC2 target `i-0664d6ea5930452db` is `Running`, type `m7i-flex.large`; EC2 instance and system status checks passed. No restart, stop, resize, or deploy was performed.
- CloudWatch `AWS/EC2` exposes 23 per-instance metric series, including CPU, network and status checks. No CloudWatch alarms exist. A reliable numeric datapoint was not captured; memory/OOM metrics were not verified.
- EBS Snapshots: 0. AWS Backup: 0 plans, 0 protected resources, 0 recovery points. SNS topics: 0.
- Billing page access was denied for the current AWS role, so current charges, credits and projected monthly backup/monitoring costs remain unknown.
- SES is still in the sandbox. Applied quota is 200 recipients per 24 hours and 1 message/second. One Gmail email identity is verified; its address is intentionally omitted. SES dashboard showed 1 sent and 199 remaining in its last-24-hour view; Service Quotas showed 0 hourly utilization in its sampled view. No production request was submitted.

### Supabase target project

- The project ref is `roznanxbiyqybjpvtilq`; the API-host fingerprint begins `44a655e04517`, matching the handoff. It is Pro, Tokyo (`ap-northeast-1`), PostgreSQL 17.11. The dashboard label is `VDaAgent`; project identity was accepted only after the fingerprint matched. No other project was changed.
- Compute is Micro (1 GB shared). Pooler size is 15; maximum client connections are 200 for this SKU. Dashboard samples showed 12–20 of 60 database connections in use.
- The dashboard Migrations view showed `0020_private_profile_retirement` only, while the handoff expected `0029_journal_intelligence`. This discrepancy is unresolved; no migration was applied.
- Auth: email confirmation, Turnstile CAPTCHA and new-user email auth are enabled; anonymous sign-ins are enabled. Limits shown include 100 sign-up/sign-in requests per 5 minutes per IP, 100 anonymous sign-ins/hour/IP, 60 verification requests/5 minutes and 150 refresh requests/5 minutes. The email-send-rate value was redacted by the browser and was not retrieved. Auth IP forwarding is off. Site URL is `https://moodprint.duckdns.org/login`; redirect allowlist contains only `https://moodprint.duckdns.org/auth/callback`.
- Custom SMTP is enabled through a Gmail host on port 465; credentials and sender address were not read. Supabase flags the provider as personal-email rather than transactional. Leaked Password Protection is disabled.
- Daily database backups are visible; latest observed capture was 2026-11-05 02:23:02 UTC. Database backup does not include Storage object bytes. PITR is a paid add-on and is not enabled. The `journal-media` bucket is private; its per-file limit is 50 MB. No Storage backup was found.

### OpenAI Platform

- The connected organization exposed only `Personal Organization → Default project`; no MoodPrint staging project was identifiable. The `gpt-6-luna` catalog card is visible, but project-level access, RPM/TPM and limits are not verified. No model was called.
- Default-project usage displayed $0.11 this month and about 3.3M tokens / 2,060 requests over 7 days; these figures are not attributable to MoodPrint staging. The project must be identified before they can support the campaign budget.
- Public GPT-6 Luna Standard short-context list rates are $0.10/M input tokens, $0.01/M cached input, and $0.50/M output. Long-context rates above 272K tokens are $0.20/M input, $0.02/M cached input and $0.75/M output. These are public list rates, not a verified account contract price: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing). The input-token counting endpoint is documented as free and does not consume inference quota; no call was made.

### Unresolved inventory facts

Billing/cost permissions, MoodPrint staging OpenAI project quotas, Supabase email rate, numeric CloudWatch samples, alarm delivery, Storage-byte backups, PITR, and restore evidence remain unverified or absent. RPO 24h/RTO 8h are targets, not achieved results.
# Fresh read-only MCP evidence — 2026-11-05 14:30–14:43 UTC

Account suffix3536, Sydney target `i-0664d6ea5930452db`: running `m7i-flex.large`,
public IPv4 `13.210.93.93`; instance/system/attached-EBS checks OK; SSM Online.
The four-hour EC2 metric window contains48 CPU points, maximum13.0002167%, mean
of period averages5.8335767%;47 StatusCheckFailed points all zero. These are
ordinary-operation metrics, **not 50-user load proof**. No CWAgent metric in this
region, no MoodPrint-prefixed alarm, and no `/moodprint`-prefixed log group returned.
Memory/disk/cgroup/5xx distributions therefore remain unknown from these APIs.

SES remains sandbox: production access false, sending enabled,200/day,1/s,
SentLast24Hours1; suppression retains BOUNCE/COMPLAINT. Attached encrypted gp3
volume30GiB has zero self-owned snapshots returned for that volume. No alarm,
snapshot, quota, identity, credential, deployment or runtime setting was changed.
API call success records and raw numeric datapoints:
[EC2/CloudWatch](evidence/ci-repair-aws-readonly.json),
[SES/EBS/SSM](evidence/ci-repair-aws-additional.json).

Refresh limitation at2026-11-05 23:xxUTC: AWS MCP returned `Unknown tool` twice,
and local AWS CLI `sts get-caller-identity` returned `NoCredentials`. No credentials
were created,read,rotated or requested. The successful14:30–14:43UTC API records
above remain historical facts;do not relabel them as a later snapshot. No target
load,cloud setting,instance state or paid operation changed during this continuation.
