# Kế hoạch EC2 t3.large, triển khai và quan sát

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

Ngày audit: 05-11-2026 (Asia/Bangkok). Phạm vi: kế hoạch, chưa thay infrastructure. Xem [baseline](01-current-codebase-audit.md), [roadmap](08-implementation-roadmap.md), [release gates](10-release-readiness-gates.md).

## AS-IS và TO-BE

| Thành phần | AS-IS, VERIFIED trong repository | TO-BE đề xuất, cần benchmark |
|---|---|---|
| EC2 | t3.large là **mục tiêu người dùng cung cấp**; instance đang chạy, region, credit mode: UNKNOWN | Một t3.large 2 vCPU/8 GiB, cùng hoặc gần region DB; giữ một API process |
| API | `deploy/compose.staging.yml:19`: 768 MiB, 1.5 CPU; grace 150 s | Bắt đầu rehearsal với 1536 MiB, CPU 1.25; tăng/giảm sau RSS và throttling; không coi là sizing đã chứng minh |
| Proactive | `deploy/compose.staging.yml:53`: 384 MiB, CPU 0.5; grace 100 s | Giữ 384 MiB, CPU 0.25, concurrency không vượt pool 2; có thể tạm dừng có kiểm soát khi overload |
| Maps | `deploy/compose.staging.yml:84`: 256 MiB, CPU 0.5; grace 30 s | Giữ 256 MiB, CPU 0.25; giới hạn job và quota riêng |
| Web/Caddy | `deploy/compose.staging.yml:111`: 256 MiB, CPU 0.5 | Giữ 256 MiB, CPU 0.25; tổng CPU limit thử nghiệm 2.0 |
| Process | `backend/app/__main__.py:9`, `:15`: một worker; graceful shutdown mặc định 45 s | Giữ một process; thống nhất drain deadline với turn timeout/leases |
| Reverse proxy | `deploy/Caddyfile:20`: flush ngay; dial 5 s, header 120 s | Giữ streaming, đo qua TLS/Caddy thật; không coi header timeout là giới hạn tổng thời gian stream |
| Health | API ready kiểm DB+revision+helper (`backend/app/main.py:360`); web kiểm Caddy admin endpoint | Kiểm thêm đường public, mã release, auth mock và một stream synthetic trước mở traffic |
| Deploy | Digest image, kiểm exact-main/CI; `deploy/aws/deploy.sh:180` dùng Compose up và rollback image | Controlled recreate có maintenance/drain; không hứa zero downtime |
| Telemetry | `deploy/aws/cloudwatch-agent.json:6` CPU/mem/disk host; alarms là template chưa được apply (`cloudwatch-alarms.json:3`) | Xác nhận metric/alarm thật; container RSS/throttling/OOM, credit, event loop, pool waits, TTFT, provider calls |

**Tính tài nguyên:** hiện tại RAM limits =768+384+256+256=1664 MiB; CPU limits=1.5+0.5+0.5+0.5=3.0 trên máy 2 vCPU. Limits không phải reservation hay mức sử dụng đo được. CPU oversubscription có thể hợp lý với I/O, nhưng thiếu bằng chứng tải hỗn hợp. Cấu hình thử ở trên dùng 2432 MiB; hai bộ container giả định 4864 MiB, cộng OS/Docker/agent/page cache. Compose hiện tại recreate cùng service, không có blue/green thực thụ; phép tính overlap là biên bảo thủ cho thao tác thủ công/khôi phục, không phải khẳng định deploy luôn nhân đôi RAM.

## CPU credits và burst/sustained

t3.large có 30% baseline, 36 credit/giờ và tối đa 864 credits. Một credit là một vCPU-phút. Nếu host CPU trung bình `u` (0..1), tốc độ rút credit `max(0,120u-36)`/giờ. Ví dụ 70% rút 48 credit/giờ, 15 phút rút 12; 100% rút 84/giờ. Đây là phép tính, không phải workload đo được. Standard có thể bị đưa về baseline khi hết credit; Unlimited có thể phát sinh phụ phí. Mode và số dư thực tế UNKNOWN. Nguồn: [AWS credit concepts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html), [Unlimited](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode.html).

Soak 15 phút chứng minh tính ổn định ngắn hạn; chưa chứng minh kinh tế CPU 24 giờ. Cần thêm soak 2 giờ mock và projection 24 giờ từ trace representative. Không tự đổi credit mode.

## Các task P4

### P4-E01 — MUST FIX / P1: đo và chốt resource envelope

- **Problem/evidence:** cap 768 MiB là trần cứng của API; chưa có RSS 50 active turns, tổng CPU limit 3.0 (`deploy/compose.staging.yml:19`, `:54`, `:85`, `:112`). **Hypothesis:** payload context, pollers và Python object growth gây OOM/throttle trước khi host hết RAM.
- **Owner:** CODEX. **Files:** `deploy/compose.staging.yml`, `deploy/runtime.env.example`, dự kiến `scripts/scale_readiness.py` (mới, task P5-L01).
- **Giải pháp:** giữ một process, thử resource envelope ở bảng; đo mock 15 phút và hỗn hợp; không tăng DB pool theo RAM.
- **Dependencies:** P0-H01, P2-D tasks, P3-I tasks, P5-L01 harness.
- [ ] Chụp baseline numeric resource limits và `docker stats`, không dump runtime env.
- [ ] Chạy 25 rồi 50 turns trên target-size staging, có giới hạn workload và cleanup.
- [ ] Thu cgroup memory.current/memory.events, RSS, CPU throttled time, loop lag và host pressure.
- [ ] Chọn limit để peak working set dưới 70% ở steady state và dưới 85% ở burst; kiểm startup cũng không OOM.
- [ ] Kiểm tổng allocation có ít nhất 2 GiB host headroom trong kịch bản triển khai đã chọn.
- **Tests/acceptance:** T4/T6/T7/T8; OOM/restart ngoài kế hoạch=0, RSS không tăng tuyến tính sau warmup, host RAM<80%, event loop p95<100 ms; CPU sustained<70% và không phá SLO khi background chạy. Đây là ngưỡng đề xuất.
- **Complexity:** M, 1–2 ngày kỹ thuật cộng rehearsal. **Risk:** giảm CPU worker có thể trễ proactive. **Rollback:** khôi phục digest/env/resource đã chụp; dừng thử và giữ maintenance nếu sức chứa thấp. **Cost:** không thêm instance; có phí thời gian staging/metrics.

### P4-E02 — MUST FIX / P1: drain và restart có contract rõ ràng

- **Problem/evidence:** Uvicorn 45 s (`backend/app/__main__.py:18`) khác container 150 s; Caddy flush âm không mặc định hủy backend khi client rời. Durable turn có thể sống lâu hơn HTTP.
- **Root/hypothesis:** các deadline được cấu hình ở các lớp riêng. **Owner:** CODEX.
- **Files:** `backend/app/__main__.py`, `backend/app/main.py`, `backend/app/ai/runtime.py`, `deploy/compose.staging.yml`, `deploy/aws/deploy.sh`, `deploy/aws/release_gate.py`, `deploy/aws/tests/test_release_gate.py`.
- **Solution/interfaces:** thêm trạng thái admission `draining` trong lifecycle, ready 503 khi drain; vẫn cho đọc/replay trong thời hạn; max turn deadline +10 s cleanup nằm trong server grace, server grace +10 s nằm trong container grace. Không tự retry paid turn sau restart.
- **Dependencies:** P3-I lifecycle/admission tasks; owner chốt có maintenance.
- [ ] Test drain chặn turn mới nhưng stream đang chạy nhận terminal hoặc trạng thái interrupted hợp lệ.
- [ ] Chốt timeout tối đa cho single/multi; tính grace theo đường dài nhất thực tế.
- [ ] Fence proactive/maps trước migration không tương thích; maintenance proxy chỉ chặn HTTP (`release_gate.py:5`).
- [ ] Recreate image cùng service; xác nhận release SHA, health, lease recovery rồi mở traffic.
- [ ] Thực hành rollback image với schema tương thích; migration rollback phải theo plan riêng.
- **Tests/acceptance:** T8; không tạo provider call trùng, ledger reconcile đúng, ready fail khi drain, terminal/interrupted sau deadline+lease; public outage mục tiêu≤180 s với maintenance. `python -m unittest discover -s deploy/aws/tests -v` trên Linux toolchain chuẩn.
- **Complexity:** M/L, 2–3 ngày. **Risk:** drain đợi vô hạn hoặc rollback image không hợp schema. **Rollback:** digest trước +config trước, giữ worker fence; không downgrade DB tùy tiện. **Cost:** downtime có kế hoạch, không tăng fixed compute.

### P4-E03 — MUST FIX / P1: telemetry và alarms đo được SLO

- **Problem/evidence:** host metrics có sẵn template nhưng không chứng minh installed; counter lines chưa cung cấp mọi distribution/gauge (`deploy/aws/cloudwatch-agent.json:1`, `deploy/aws/cloudwatch-alarms.json:3`, `backend/app/main.py:96`).
- **Root:** observability cho scale cần thêm dữ liệu và xác nhận vận hành. **Owner:** CODEX cho code/template; HUMAN apply bằng P0-H03.
- **Files:** `backend/app/core/logs.py`, `backend/app/main.py`, `backend/app/ai/provider.py`, `backend/app/infrastructure/database/connection.py`, `deploy/aws/cloudwatch-agent.json`, `deploy/aws/cloudwatch-alarms.json`.
- **Solution:** histogram request/TTFT/completion/pool wait, gauges admitted/actual provider active/SSE by route, CPU credits native `AWS/EC2`; không log prompt/email/token/DSN. Stream count social hiện có không đại diện mọi AI stream.
- **Dependencies:** định nghĩa metrics P5-L01 và plan AI/DB.
- [ ] Test mỗi outcome emit đúng một metric và không chứa PII.
- [ ] Thêm instrumentation checkout wait, provider start/end/cancel, turn admission/reject, SSE open/close.
- [ ] Thêm alarm CPUCreditBalance dự báo cạn<2 h; surplus charged>0; container memory>85%, OOM>0, 5xx>1%, TTFT p95>5 s; thiếu mẫu phải UNKNOWN.
- [ ] Dùng canary không trả phí kích hoạt cảnh báo và kiểm dashboard/notification đến owner.
- [ ] Đặt retention/cost budget cho logs; labels chỉ route/status/workflow, tránh user ID cardinality.
- **Tests/acceptance:** đủ toàn bộ metrics ở [T1–T8](07-load-testing-and-benchmark-plan.md); alarm có timestamp delivery; tỷ lệ 5xx là errors/requests cùng cửa sổ, không thay bằng absolute count.
- **Complexity:** M, 2 ngày. **Risk:** metric cardinality/ingest cost. **Rollback:** tắt emit mới theo flag, giữ base logs; owner gỡ alarm mới theo manifest. **Cost:** CloudWatch logs/custom metrics/alarms tăng theo bảng giá region, chưa có estimate USD đáng tin.

## Capacity alternatives và trigger

| Phương án | Khi chọn | Bằng chứng bắt buộc | Trade off/cost |
|---|---|---|---|
| A: tối ưu single EC2 | Mặc định cho mục tiêu hiện tại | T4–T8 pass; loop/RSS/CPU/DB đạt gates | Ít thành phần nhất; host vẫn SPOF |
| B 1: tăng EC2 | Sau tối ưu A vẫn CPU>70%15 phút +loop lag>100 ms/p95 hoặc OOM ở trần hợp lý; model/DB không nghẽn | Trace CPU/RSS/throttle; repeat cùng dataset và provider/mock | Tăng instance bill; stop/resize có downtime; nếu sustained vượt baseline nên so fixed CPU family; không mặc định t 3.xlarge giải quyết mọi vấn đề |
| B 2: tăng Supabase compute | DB CPU>70%/IO wait/saturation hoặc memory áp lực trong khi pool/queries đã tối ưu | Query plans, DB waits, compute/role limits từ owner | Thêm compute billing; role 20 không tự tăng theo plan |
| C: thêm tối thiểu component | Cần HA khi RTO không chịu được host mất, hoặc bắt buộc nhiều API process sau tối ưu | Fail over/RTO và admission/state design được test, business chấp nhận cost | Chỉ lúc đó xét process/host thứ hai và shared coordination; DB queue hiện có được ưu tiên trước Redis/SQS. Không thêm Kubernetes/ECS để đạt benchmark |

Nếu bottleneck là upstream 429/TPM, email quota hay reservation $2 thì upgrade EC2 không giải quyết. [Capacity](02-capacity-and-bottleneck-analysis.md) cung cấp công thức quyết định.

## Nguồn và version caveat

Repo pin Caddy 2.10.2 (`frontend/Dockerfile:10`). [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) hiện mô tả cả tính năng mới hơn; chỉ dùng semantics flush/header-timeout đã tồn tại, phải verify hành vi với image pin khi thực thi. Không tự nâng image trong audit. Giá EC2/EBS/egress cần region/OS/credit mode thật tại [AWS EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/).
