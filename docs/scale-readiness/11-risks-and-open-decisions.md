# Rủi ro và quyết định còn mở

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

Ngày 05-11-2026. Các quyết định dưới đây chưa phải permission request để triển khai trong phiên audit. Owner có thể cung cấp facts không nhạy cảm theo [09](09-human-action-checklist.md); implementation chỉ bắt đầu trong nhiệm vụ riêng. [Summary](00-executive-summary.md), [roadmap](08-implementation-roadmap.md), [gates](10-release-readiness-gates.md).

## Risk register

| ID / mức | Rủi ro, bằng chứng | Khả năng / tác động | Mitigation / owner | Trigger và rollback |
|---|---|---|---|---|
| R01 P0 | NAT 100 bị shared 40/900 (`backend/app/modules/auth/routes.py:228`) | Chắc theo code nếu bucket sạch; signup legitimate bị chặn | P1-A02, HUMAN chốt policy | T3<100; giữ guard/cooldown, không tăng vô điều kiện |
| R02 P0 | Lower reserve sai làm vượt cap 20; hiện $2/row (`backend/app/ai/accounting.py:24`) | Thay đổi code financial rủi ro cao; bill khó hoàn tác | Bound/tokenizer/max calls phải enforce trước wire, atomic ledger; CODEX P3-I02 | Any under reserve/unknown price→stop new admission, rollback version bound $2, giữ liability |
| R03 P0 | Provider RPM/TPM hoặc SES quota không đủ | UNKNOWN likelihood; broad outage/throttle | HUMAN limits proof, controlled T2/T5 |429>1%legitimate cohort; no-go, không retry/scale EC2 để che |
| R04 P1 | Role/pooler thấp hơn assumption 20, overlap 16 | SQL bootstrap 10, cloud UNKNOWN; exhaustion | P2-D01/D02, chọn topology và maintenance reserve | Pool wait/timeout→stop load, old reviewed pool/config; không auto ALTER role |
| R05 P1 | Polling/auth revalidation áp lực DB | INFERRED 300 vòng/s 50 saved stream+run; latency/lock | P2-D03, đo query/RTT/cache bounded authorization |Wait p95>100 ms/no SLO→giảm poll work giữ revocation; revert optimization nếu leak |
| R06 P1 | API 768 MiB OOM/loop lag hoặc T3 credits | Chưa đo; mất SSE và ephemeral state | P4-E01, resource/cgroup/credits metrics |OOM>0/CPU pressure→stop test, previous digest/resource; B resize chỉ khi đúng bottleneck |
| R07 P1 | Chỉ đóng SSE nhưng provider vẫn chạy | `chat_routes.py:769`, Caddy flush-1; residual cost | P3-I05, explicit cancel contract/retained reservation |Disconnect trace có orphan→cancel/reconcile; không coi EOF refund |
| R08 P1 | Child/journal/proactive chiếm registered capacity | `journal_memory.py:298`, global count mọi origin | P3-I03/I06 fairness/quotas, giữ shares |T7 registered reject→defer background theo policy; không bỏ ledger |
| R09 P1 | False PASS từ fake/live script 12/fixture pool 5+5 | Scripts scope đã xác minh | P5 manifest/measurement, 50 barrier+15 min |Thiếu data/config khác→invalidate run, không gộp result |
| R10 P1 | Một EC2 là SPOF, deploy recreate không HA | `deploy/aws/deploy.sh:180` | Owner chấp nhận RTO/maintenance, backup+restore+rollback |Business RTO không chịu outage→mở option C sau architecture state/fencing review |
| R11 P1 | Wrong proxy trust tạo IP collapse/spoof | `backend/app/__main__.py:10`; actual FORWARDED_ALLOW_IPS UNKNOWN | P1-A03 xác minh full chain; không tin từ browser |Trust test fail→publishable egress mode/admission conservative, giữ antiabuse |
| R12 P1 | Secret local scratch đã xuất hiện trong read output | `backend/runtime.txt` chứa credential, không copy value | HUMAN rotate và quản lý scratch, audit không sửa.gitignore |Credential leak→coordinated rotation, không xóa evidence hay in value |
| R13 P2 | Storage/vector/session growth vượt forecast | Journal media 10/20/50 MiB perfile, retention scope khác | T1 forecast 90 ngày, P2-D06/D07/D10 |Disk>70%forecast/retention lag→batch cleanup owned expired+resize được review; không purge user bừa |
| R14 P1 | Thiếu usage/crash refund làm under billing guard | `accounting.py:162`, uncertain carryover | P3-I08 fault matrix/reconciliation |Usage unknown→retain reserve/deny new when needed, no auto reset at midnight |
| R15 P2 | Provider pricing/version thay đổi | Dynamic external docs; code pricing version pin | HUMAN chụp pricing tại release, canary/check version |Price/model unrecognized→fail closed, không cho estimated average override |

## Open decisions

| ID | Câu hỏi cần chốt / facts thiếu | Khuyến nghị hiện tại | Người quyết định / task bị chặn |
|---|---|---|---|
| D01 | Supabase compute SKU/region/actual DB/pooler/role limit? | Lấy read-only facts; không suy Pro=SKU cố định | HUMAN H-S01/S 06; P2-D01/G01/G06 |
| D02 | SES region, sandbox/production, quota/rate, SMTP/CAPTCHA/redirects? | Custom SMTPSES, confirmed flow giữ; ≥5/s và 3000 recipient/24 h là proposal để review | HUMANH-M/H-S; P1-A08/G04/G05 |
| D03 | Policy cho 100 legitimate users cùng NAT? Có event network? | Tách IP abuse ceiling/email action/risk/CAPTCHA; chấp nhận rõ thời gian chờ nếu không đủ | HUMAN product/security; P1-A02/T3 |
| D04 | Upstream Auth dùng publishable egress hay secret key forward IP? | Đo egress/trust trước; secret chỉ server và review endpoint/CAPTCHA, không admin auto-confirm | HUMAN+CODEX P1-A03 |
| D05 | Context/output/calls envelope được chấp nhận để 50 trong cap 20? | Bounded input+max output+all child/tool cost, nếu upper bound không đủ tiền giữ NO-GO | HUMAN product+CODEX financial review; P3-I02/G07 |
| D06 | Provider limits actual org/project/model/tier? | Ghi RPM/TPM/long context/shared limits+30%headroom từ trace; không dựa vào public tier | HUMAN H-O01/P3-I09/G09 |
| D07 | Daily usage 1000 users, tỷ lệ single/multi/group, token distribution? | Chốt mean/p95/context/calls; scenario 1/10/60 turn để thấy cap 20 khác storage capacity | HUMAN product; capacity/cost acceptance |
| D08 | TTFT nghĩa provider first token hay client raw token? | Đo provider TTFT và client first progress/final riêng; hiện client không raw token stream | HUMAN product+CODEX P3-I04; G08/G09 |
| D09 | Quota/budget scope có Voyage/STT/maps và guest/proactive? | Explicit per origin and provider budget, không tuyên bố ap p20 bao mọi hóa đơn | HUMAN finance+CODEX P3-I06 |
| D10 | RPO/RTO/maintenance và SPOF có chấp nhận? | RPO 24 h/restore test nếu daily backup, đề xuất maintenance RTO≤180 s; host fail RTO phải đo, không hứa 180 s | HUMAN operations; P0-H02/P4-E02/option C |
| D11 | Thực tếEC 2 region/type/credits/CPU/RSS/EBS và deployed SHA? | Chốt before/after resource facts, single API process | HUMAN H-E01…03; P4-E01 |
| D12 | Ai approve paid/hosted tests, target/cap/time window/cleanup? | T5≤$5/run, app cap 20 giữ; nếu profile không vừa cap thì không chạy và owner chốt phạm vitest | HUMAN H-O03/P5-L02/G09 |
| D13 | Backup Storage objects và xóa session retention mong muốn? | DB backup riêng Storage backup, purge expired sessions batch; giữ unknown liability | HUMAN privacy/ops+P2-D07/D10 |

## Architecture alternatives A/B/C

- **A tối ưu single EC2:** mặc định, giữ stack và process model. Sửa reservation/admission/query/polling/metrics, tăng RAM container nếu trace cần. Ưu điểm ít component, nhược SPOF và một event loop.
- **B upgrade EC2 hoặc Supabase compute:** sau A nếu CPU/loop lag/RSS hoặc DB wait/IO là bottleneck đo được. EC2 resize không sửa SES/Auth/OpenAI quotas hoặc cap 20; DB resize không tự đổi role limit. Cần estimate region bill+credits và rehearsal downtime.
- **C thêm tối thiểu hạ tầng:** chỉ khi yêu cầu HA/RTO hoặc bottleneck bắt buộc nhiều process sau A/B. Ưu tiên reuse DB queue/lease hiện có; shared state/fencing/limiter/cost reservation phải đúng trước scale horizontally. Không mặc định Redis/SQS/ECS/Kubernetes.

Trigger thresholds và resource proposal tại [06](06-ec2-t3-large-deployment-plan.md). Khi quota/provider latency chi phối, giữ A và xử lý đúng quota hoặc admission; không chọn B/C theo số người dùng đăng ký.

## Thông tin chưa có và giới hạn kết luận

Không có runtime/cloud read được xác minh, production traffic/profile, resource/cost trace, deliverability timeline, actual provider quotas, DB EXPLAIN/RTT, backup restore proof hoặc completed T1–T8. Do đó không có benchmark thật để cam kết t3.large đủ, chi phí tháng cụ thể hay date production release. Mọi UNKNOWN quan trọng giữ gate tương ứng open; roadmap đã quy định cách lấy evidence, không yêu cầu dán secrets.
