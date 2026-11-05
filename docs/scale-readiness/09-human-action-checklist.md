# Checklist thao tác HUMAN và bằng chứng cần thu

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

Ngày 05-11-2026. **Tất cả checkbox đang mở**: audit chưa thay cloud, gửi email, tạo hosted user, gọi paid provider hay deploy. [Roadmap](08-implementation-roadmap.md) xác định phụ thuộc; [gates](10-release-readiness-gates.md) quyết định release. Tên menu có thể đổi; dùng chức năng được nêu nếu Console khác nhãn.

`UNKNOWN` là chưa có bằng chứng từ đúng project/instance. Supabase Pro đã mua là thông tin người dùng cung cấp; không suy ra compute, SMTP hay quota. Không cần dán secret vào chat: chỉ trả các giá trị không nhạy cảm, trạng thái và timestamp.

## Supabase

| ID/check | Console/đường dẫn | Hiện tại | Đề xuất và lý do | Cách kiểm tra/bằng chứng không nhạy cảm | Downtime/cost | Secret nhập ở đâu |
|---|---|---|---|---|---|---|
| [ ] H-S01 compute/region | Project → Settings/Infrastructure → Compute and Disk; Connect | UNKNOWN | Ghi compute SKU, RAM, DB region, pooler region; so RTT với EC2 | Export tên SKU/region và max connections; không chụp connection string | Read-only 0; resize có restart/phí | Không cần |
| [ ] H-S02 Auth limits | Authentication → Rate Limits | UNKNOWN | Đối chiếu signup 100/60 s, verify/login/resend; không tắt anti-abuse | Ghi từng endpoint/rate/window, custom SMTP limit và email cooldown; xác nhận proxy egress/forwarded IP plan | Tăng quota có rủi ro abuse; chỉ sau review | Secret server key nếu chọn forwarded IP ở Secure String, không web |
| [ ] H-S03 SMTP | Authentication → Email/SMTP Settings | UNKNOWN | Custom SMTP tới SES đúng region, sender domain verified; không dùng mail mặc định cho burst | Test riêng có phê duyệt: signup accepted→Auth created→SES accepted→delivered→confirmed; chỉ count/latency/redacted ID | Phí SES; không downtime dự kiến | SMTP user name/password chỉ trong dashboard SMTP, không backend repo |
| [ ] H-S04 CAPTCHA | Authentication → Attack Protection/CAPTCHA; Turnstile dashboard | UNKNOWN | Bật CAPTCHA cho đăng ký/recovery đúng trust path, site key origins khớp domain | Synthetic valid/invalid/expired token; xác nhận frontend hiển thị widget và CSP | Có thể chặn signup nếu sai; thử staging trước | CAPTCHA secret trong Supabase; site key public trong runtime config theo app; không dán chat |
| [ ] H-S05 providers/redirects | Authentication → Sign In/Providers; URL Configuration; Email Templates | UNKNOWN | Email confirmation bật; URL s HTTPS exact allowlist; password/reset policy giữ nguyên | Signup/confirm/login/recover/logout một account controlled; không tạo 100 user trong audit | Phí email nhỏ; sai URL khóa onboarding | Provider secret chỉ dashboard provider |
| [ ] H-S06 DB budget | SQL Editor hoặc DB read-only console, Connect/Pooler | role 20 là assumption; SQL provisioning 10; actual UNKNOWN | Đo `rolconnlimit`, `max_connections`, pooler client/server limits; budget steady 8/overlap 16 +reserve 4 chỉ hợp lệ nếu role≥20 và server đủ | Chạy SELECT review ở [DB plan](04-database-and-connection-pooling-plan.md); trả numeric, không DSN | Read-only 0; ALTER role cần review riêng | Runtime DB DSN root-owned SSM Secure String; migration credential riêng |
| [ ] H-S07 RLS/grants | Database → Tables/Policies; API/Data API settings | Repository có bootstrap, hosted UNKNOWN | Role runtime tối thiểu, không BYPASSRLS; private schema không expose ngoài chủ đích | Catalog grants/RLS/role flags redacted; test cross-user isolation | Có thể gián đoạn nếu đổi grant; migration được review | Owner migration credential chỉ runner kiểm soát |
| [ ] H-S08 backup/PITR | Database → Backups/Point in Time Recovery | UNKNOWN | RPO≤24 h nếu daily backup; muốn≤15 phút cần PITR đã mua và test. Storage object backup riêng | Timestamp latest backup +restore rehearsal trên project khác; ghi RPO/RTO thực đo | Restore/upgrade PITR có phí/downtime; không restore production để thử | Backup secret trong vault, không docs |
| [ ] H-S09 storage | Storage → journal-media → Settings/Policies; Usage | UNKNOWN | Private bucket; type/size caps khớp repo; kiểm usage/egress và retention | Signed read hết hạn, anonymous denial, orphan cleanup controlled, byte counts | Storage/egress có phí; không xóa object user | `JOURNAL_STORAGE_KEY` ở SSM backend  |

## AWS SES

| ID/check | Console/đường dẫn | Hiện tại | Đề xuất và lý do | Kiểm chứng | Downtime/cost | Secret nhập ở đâu |
|---|---|---|---|---|---|---|
| [ ] H-M01 region/access | SES → Account dashboard, chọn đúng Region | UNKNOWN | Production access cho recipient thật; "Essentials" không chứng minh đã ra sandbox | Ghi Production Access Enabled, sending enabled, region, quota 24 h/max send rate | Request review có thời gian chờ, email bill | Không cần |
| [ ] H-M02 identity/DNS | SES → Configuration → Verified identities → domain; DNS provider | UNKNOWN | Verified domain +Easy DKIM; custom MAIL FROM/SPF đúng; DMARC theo rollout | DNS lookup DKIM/SPF/DMARC, SES verification status; kiểm header test được phê duyệt | DNS propagation, không downtime app | DNS quyền hẹp trong DNS Console; không chat |
| [ ] H-M03 quota | SES → Account dashboard → Sending quotas; Service Quotas → SES | UNKNOWN | ≥5 accepted recipient/s để có headroom so 100/60 s=1.67/s; quota 24 h≥3000 recipient cho onboarding 1000 +retries/resend được giới hạn; đây yêu cầu đề xuất | Ghi quota thật và consumed 24 h; kiểm Supabase SMTP cap cũng đạt 100/60 s. Mọi resend tính vào budget | Quota thường không phải phí fixed, usage tăng | Không cần |
| [ ] H-M04 SMTP credentials | SES → SMTP settings → Create/manage SMTP credentials | UNKNOWN | Region-specific SMTP TLS; least privilege; xoay theo quy trình | Connection/Auth smoke đã duyệt, không hiển thị password; đối chiếu endpoint region | Rotate sai có thể dừng mail; SES bill | Supabase Custom SMTP form; lưu vault/SSM operator nếu cần, không frontend/.env commit |
| [ ] H-M05 bounce/complaint | SES → Configuration sets → Event destinations; Reputation metrics | UNKNOWN | Track SEND/DELIVERY/BOUNCE/COMPLAINT/REJECT/DELAY; owner nhận alert qua kênh đã chọn | Test bằng SES mailbox simulator sau approval; đếm provider Message ID qua event mapping, không lưu email | Event destinations/CloudWatch/SNS có phí tùy lựa chọn; không tự thêm service | Event sink credential ở managed secret store |
| [ ] H-M06 suppression | SES → Account-level suppression; Verified identities | UNKNOWN | Giữ suppression list; không xóa hàng loạt để nâng success rate | Kiểm test recipient controlled; bounce giải thích được; xử lý complaint với owner | Không downtime, ảnh hưởng deliverability | Không cần |

1000 registered không đồng nghĩa 1000 email/ngày mãi mãi. Sending quota đếm recipient theo 24 h; retries/resends và test dùng chung quota. [SES quotas](https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html), [sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html), [SMTP credentials](https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html).

## EC2/operations

| ID/check | Console/đường dẫn | Hiện tại | Đề xuất/lý do | Kiểm chứng | Downtime/cost | Secret nhập ở đâu |
|---|---|---|---|---|---|---|
| [ ] H-E01 target identity | EC2 → Instances → Instance details | Targett3.large; actual UNKNOWN | Xác nhận account/region/instance ID/type 2 vCPU 8 GiB, OS/EBS, domain mapping | Chụp field không nhạy cảm, release SHA/container limits; che IP nếu chia sẻ công khai | Read-only 0 | Không cần |
| [ ] H-E02 backup/resize | EC2 → Volumes → Snapshots; AWS Backup nếu đang dùng | UNKNOWN | Snapshot EBS trước thay đổi; bảo vệ Caddy data/config; restore rehearsal | Snapshot Completed, encrypted, restore test; người chịu trách nhiệm và thời điểm | Snapshot/storage bill; resize thường stop/start có downtime | Không cần |
| [ ] H-E03 CPU credits | EC2 → Instance → Monitoring/Actions → Credit specification; CloudWatch AWS/EC2 | UNKNOWN | Giữ mode hiện tại cho tới khi đo; alarm balance/surplus; tính 24 h | `CPUUtilization`, `CPUCreditBalance`, `CPUSurplusCreditBalance`, `CPUSurplusCreditsCharged` cùng trace | Unlimited có phụ phí, Standard có throttling | Không cần |
| [ ] H-E04 CloudWatch | CloudWatch → Metrics/Logs/Alarms; Systems Manager → Run Command/agent | Templates trong repo; installed UNKNOWN | Apply reviewed metrics/alarms, retention và cost budget; delivery đến owner | Canary tạo metric và alarm thực; dashboard TTFT/provider/pool/RSS | Logs/custom metrics/alarms có phí | Notification channel cấu hình tại AWS, không gửi tin nhắn tự động trong audit |
| [ ] H-E05 IAM/SSM | IAM → Role attached to EC2; Systems Manager → Fleet Manager/Session Manager | Repo có policy template; actual UNKNOWN | Least privilege Get Parameter đúng path, SSM managed role, IMDS v 2; không mởSSH rộng | Session Manager hoạt động; Cloud Trail lookup redacted; không in Secure String | Cấu hình sai làm mất quản trị; phí log tùy setup | AWS credentials dùng SSO/role, không chat |
| [ ] H-E06 secrets | Systems Manager → Parameter Store → runtime Secure String | Deployment code đọc file 0600; actual UNKNOWN | Root owned runtime, không dump Compose environment; tách migration/runtime/provider keys | Chỉ ghi key set allowlist và trạng thái configured; không chụp value | Rotation cần phối hợp, có thể mail/DB downtime nếu sai | Nhập trực tiếp Secure String/vault; SMTP riêng trong Supabase |
| [ ] H-E07 deploy/rollback | Git Hub → Actions; EC2 → SSM; `/opt/moodprint` | Code có hold/provenance/rollback; installed UNKNOWN | Không remove hold khi chưa qua [gates](10-release-readiness-gates.md); maintenance/drain trước thay đổi | Exact SHA/digest, readiness public, test SSE, rollback rehearsal | Controlled downtime, không gọi là rolling HA | Release-test token chỉ Secure String |
| [ ] H-E08 credential hygiene | Local `backend/runtime.txt`; vault và database credential settings | File local có credential; chưa commit | Xoay credential đã xuất hiện trong output đọc file; owner xử lý scratch an toàn, không sửa.gitignore | Xác nhận credential cũ hết hiệu lực và ứng dụng dùng credential mới, không trả value | Có rủi ro gián đoạn DB nếu đổi không phối hợp | Vault/Secure String/runtime file root owned, không chat/docs |

## OpenAI và provider phụ

| ID/check | Console/đường dẫn | Hiện tại | Đề xuất/lý do | Kiểm chứng | Downtime/cost | Secret nhập ở đâu |
|---|---|---|---|---|---|---|
| [ ] H-O01 limits/model | OpenAI Platform → Settings → Organization/Project → Limits | Local config có model; production model/tier/RPM/TPM UNKNOWN | Ghi đúng org/project/model endpoint, RPM/TPM/long context limits; có headroom≥30% so [capacity](02-capacity-and-bottleneck-analysis.md) | Export numeric limits, headers request ID redacted; không dùng tier quảngcáo thay quota project | Rate increase cần review, không tự nâng tier | Project API key trong SSM backend |
| [ ] H-O02 spending | Platform → Usage; Billing → Limits/Budgets | Local cap 20 +accounting; provider budget UNKNOWN | Giữ app cap 20 nếu đang bật; alert 50/80/100%; provider budget có thể chỉ alert, không thay hard cap | Ledger reconcile với Usage theo UTC/provider day và Asia/Bangkok app day; ghi estimated/actual | Paid T5 chỉ sau owner approval+run cap riêng≤$5 | Không cần secret trong report |
| [ ] H-O03 live test | Owner chọn staging/run window trong [T5](07-load-testing-and-benchmark-plan.md) | Chưa approved/chưa chạy | Phê duyệt project, target, 50 users, 15 phút, token max, cost cap, cleanup, stop operator trước chạy | Bản approval+run manifest, ledger≤cap, kênh dừng sẵn | Paid tokens/egress; budget 20 có thể không đủ cho profile nặng | Scoped project key trong runner env ngoài repo |
| [ ] H-O04 embeddings/voice/search | Voyage/OpenAI/Apify project dashboards tương ứng | Actual quota/pricing UNKNOWN | Ghi quotas/caps/flags và spending pool; background không chiếm hết interactive budget | Trace T7 phân loại calls/tokens per origin, không prompt/PII | Phí provider phụ, tắt theo plan có thể giảm feature | Backendmanaged secrets; không frontend |

[OpenAI limits](https://developers.openai.com/api/docs/guides/rate-limits), [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase). Giá/quota là thông tin động: owner chụp timestamp bằng chứng ngay trước release.

## Gói thông tin có thể gửi lại an toàn

- [ ] Supabase compute SKU/region/role connection limit/pooler caps, DB size và RPO/RTO.
- [ ] Auth endpoint limits, SMTP configured, CAPTCHA enabled; SES production/sandbox, region, max send rate/quota 24 h.
- [ ] EC2 type/region/credit mode/balance, resource usage và deploy SHA/digest.
- [ ] OpenAI model và numeric RPM/TPM/budget/usage; tỷ lệ single/multi agent, token percentiles, daily turns dự kiến.
- [ ] Quyết định NAT policy, maintenance window, acceptable RTO/RPO và người approve paid test.

Không cần URL chứa password, SMTP password, API key, email người dùng hay prompt thật. Các giá trị hiện UNKNOWN giữ release gate mở.
