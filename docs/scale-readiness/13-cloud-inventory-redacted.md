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
