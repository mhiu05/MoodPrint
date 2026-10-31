# 91 — Hiệu năng, chi phí và dung lượng

> **Phân biệt rõ:** "Đo được" = số liệu tổng hợp đọc từ hosted DB trong phiên này (Supabase MCP, chỉ aggregate). "Giả định" = ước lượng cần đo lại khi triển khai. Không có benchmark nào được chạy.

## 1. Baseline đo được (hosted, 30 ngày, n = 65 row `ai_usage`)

| Chỉ số | Giá trị |
| --- | --- |
| Input token trung bình / run | **1.659** |
| Output token trung bình / run | **172** |
| Model call trung bình / run | **1,11** (giới hạn 3) |
| Run trong 7 ngày | 116 (~16,6/ngày) |
| Người dùng registered active (thấy trong 7 ngày) | 6 |
| Hội thoại đã lưu còn hạn | 7 |
| Nhật ký đã lưu | 0 |

Không đo được: độ trễ model (log CloudWatch không truy cập được vì AWS MCP lỗi), tỷ lệ cached token.

## 2. Đơn giá

Bảng giá trong repo: `RATES["gpt-6-luna"] = (100, 10, 500)` nano-USD/token cho input, cached input, output (`PRICING_VERSION = "openai-standard-2026-10-24"`, [accounting.py:12-14](../../../backend/app/ai/accounting.py#L12)) — tức $0,10 / $0,01 / $0,50 cho 1 triệu token. **Chưa đối chiếu lại** với bảng giá OpenAI trong phiên này; mọi con số dưới đây tỷ lệ tuyến tính với đơn giá.

Công thức (giống `persist_snapshot`):

```text
cost_nano = (input − cached) × r_in + cached × r_cached + output × r_out
```

## 3. Chi phí một lượt

| Loại lượt | Input | Output | Chi phí (nano-USD) | USD | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| Chat hiện tại (đo được) | 1.659 | 172 | 1.659×100 + 172×500 = **251.900** | $0,00025 | Giả định cached = 0 (cận trên) |
| Chat nhiều bubble | +90 (hướng dẫn tách) | +10 (JSON wrapper) | +14.000 (**+5,6 %**) | — | Giả định 1,4 bubble trung bình |
| Lời hỏi thăm (trung bình) | ~1.350 | ~180 | 1.350×100 + 180×500 = **225.000** | $0,000225 | Giả định: instructions ~1.100 + lớp proactive ~250, payload nhỏ |
| Lời hỏi thăm Nhịp có 3 entry (cận trên) | ~1.900 | ~220 | **300.000** | $0,0003 | Excerpt 3×600 ký tự |
| Cộng tác `nhip_energy_for_rure` (phần thêm) | specialist ~1.100 + primary +40 | ~30 | 1.100×100 + 30×500 + 40×100 = **129.000** (**+51 %** so với chat) | $0,00013 | |
| Cộng tác `nhip_habit_for_may` (phần thêm) | specialist ~380 + primary +90 | ~80 | 38.000 + 40.000 + 9.000 = **87.000** (+35 %) | $0,00009 | |

## 4. Chi phí theo ngày (proactive)

Công thức: `daily = users × enable_rate × slots_per_user × cost_proactive × (1 + retry_rate)`, với `retry_rate` giả định 5 %.

| Kịch bản | Giả định | Lượt/ngày | USD/ngày | USD/tháng |
| --- | --- | --- | --- | --- |
| Hiện tại | 6 users, 50 % bật, 2 khung | 6 | $0,0014 | $0,04 |
| Beta | 100 users, 60 %, 2 khung | 120 | $0,028 | $0,85 |
| Mở rộng | 1.000 users, 60 %, 2,5 khung | 1.500 | $0,35 | $10,6 |
| Trần cap | 1.000 users × 4 khung, toàn Nhịp có nhật ký | 4.000 | $1,26 | $38 |

So sánh: chat hiện tại ~16,6 lượt/ngày × $0,00025 ≈ $0,004/ngày. `PROACTIVE_BUDGET_SHARE = 0,5` của `AI_DAILY_BUDGET_USD` là trần cứng.

Cộng tác (Phase 2): trần 10 lần/user/ngày ⇒ tối đa ~$0,0013/user/ngày. Beta (100 users, 20 % bật, 2 lần/ngày): 40 × 129.000 nano ≈ $0,005/ngày.

## 5. Model call và budget

| Lượt | Model call | Tool call | `max_turns` |
| --- | --- | --- | --- |
| Chat một trợ lý | 1,11 TB (đo), ≤ 3 | ≤ 2 | 3 |
| Chat có cộng tác | +1 specialist ⇒ ~2,11 TB, ≤ 4 tuần tự | primary ≤ 2, specialist 0 | primary 3, specialist 1 |
| Lời hỏi thăm | 1 (≤ 2) × attempts ≤ 3 | 0 | 2 |
| Lời hỏi thăm Rủ Rê có cộng tác (R2) | 2 | 0 | 2 + 1 |

Độ sâu tối đa: 1. Không có vòng lặp: specialist không có coordinator; unique `(primary_run_id, specialist_bot, edge)`.

## 6. Độ trễ

```text
T_turn        = T_admission + Σ T_model_i + Σ T_tool_j + T_publish
T_turn_collab = T_turn + T_authorize (2 transaction ngắn) + T_model_specialist + T_settle
```

| Thành phần | Giả định | Cách đo khi triển khai |
| --- | --- | --- |
| `T_model` p50 / p95 | 1,5–3 s / 4–8 s | `ai_execution_end duration_ms`, `first_progress_ms` ([runtime.py:762](../../../backend/app/ai/runtime.py#L762)) |
| `T_model_specialist` (≤ 300 token output) | p50 1–2 s, cắt cứng 8 s | Metric `collaboration_state duration_ms` |
| `T_authorize` + `T_settle` | 20–80 ms | Log request |
| Ngân sách tổng | 30 s (hiện có) | Coordinator bỏ phối hợp nếu còn < 15 s |

Mục tiêu P2-NFR-01: p95 thêm ≤ 4 s.

## 7. Thông lượng worker

```text
jobs_per_minute ≈ 60 × c / T_job,   T_job ≈ T_model + 0,2 s DB
```

| `PROACTIVE_WORKER_CONCURRENCY` (c) | `T_job` = 4 s | Số job đến hạn cùng phút giao xong trong 10 phút (P1-NFR-01) |
| --- | --- | --- |
| 1 | 15/phút | ≤ 150 |
| 2 | 30/phút | ≤ 300 |
| 4 | 60/phút | ≤ 600 |

Beta (≤ 100 users, ≤ 400 job/ngày, giờ phổ biến 07:00–07:30): c = 1 đủ. Tăng c theo metric `proactive_queue_due` và `proactive_lag_seconds`, không vượt `ai_global_concurrency`.

## 8. Database

> Cập nhật: topology mới (service `proactive` riêng, pool 2+0) và công thức ngân sách kết nối ở [96 §4](96-architecture-hardening-review.md#4-ngân-sách-kết-nối-supabase) thay cho đoạn "không thêm engine" dưới đây.

- **Kết nối**: không thêm engine. Worker dùng tối đa `c + 1` checkout ngắn trong pool 5+2 của process; khi deploy chồng 2 process: 14 ≤ role limit 20 (headroom 6 ≥ `MINIMUM_HEADROOM = 4`, [budget.py](../../../backend/app/infrastructure/database/budget.py)). Hosted lúc kiểm: 15 kết nối `moodprint_backend` (12 idle, 3 *idle in transaction*) — cần làm rõ nguồn trước khi tăng tải ([94](94-dependencies-risks-and-open-decisions.md) R-06).
- **Ghi**: mỗi job ~6 transaction, ≤ 11 row (job, run, turn, usage, 1–3 message, 0–3 source, 0–1 conversation). Kịch bản 1.500 job/ngày ⇒ ~16.500 row/ngày; job giữ 30 ngày ⇒ ~45.000 row. Không đáng kể với PostgreSQL 17.
- **Đọc inbox**: một truy vấn nhóm mỗi 30 s/tab hiển thị; index `ai_runs(user_id, origin, created_at)` + `ai_messages(run_id)`.

## 9. Tài nguyên EC2

| Hạng mục | Ước lượng | Căn cứ |
| --- | --- | --- |
| RAM thêm | < 20 MB (payload ≤ 30 KB/job, object SDK tạm thời) | Worker trong process, c ≤ 4 |
| CPU thêm | Không đáng kể (Pydantic/JSON < 10 ms/job; model call là I/O) | — |
| Giới hạn container | `api`: 768 MB, 1,5 CPU ([compose.staging.yml](../../../deploy/compose.staging.yml)) | Đọc từ repo |
| Loại instance, mức dùng hiện tại | **Chưa biết** — AWS MCP không kết nối | Trước khi bật worker: CloudWatch `mem_used_percent` p95 < 70 %, `cpu_usage_active` p95 < 50 % trong 7 ngày |

Kết luận: EC2 hiện tại **có khả năng** chạy worker trong process ở quy mô beta, **với điều kiện** kiểm chứng hai metric trên (chưa làm được trong phiên này).

## 10. Số đo Phase 1 (31/10/2026, local + AWS/Supabase chỉ đọc)

### 10.1 Tải worker (`scripts/load_proactive.py`)

Một máy Windows (API in-process pool 5+2, worker **process riêng** như service `proactive`, PostgreSQL 17 container cùng máy), model giả trễ 1,5 s cho cả chat và lời hỏi thăm, 20 người chat đồng thời × 3 lượt chạy **song song** với N lịch đến hạn cùng lúc. Chat đo hai lần không có worker (lần đầu làm nóng; lần đầu tiên chưa làm nóng cho +36 % là sai số khởi động nên đã đổi phương pháp).

| N lịch | Concurrency | Pool worker | Chat p95 không worker → có worker | Lag giao p50 / p95 | Thông lượng | Pool peak | RSS peak worker | Kết nối PG peak | Transaction dài nhất |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 1 | 2+0 | 3,13 → 3,37 s (+7,5 %) | 23 / 36 s | 35/phút | 1 | 145 MiB | 7 | 0,15 s |
| 20 | 2 | 2+0 | 3,19 → 3,43 s (+7,7 %) | 15 / 22 s | 66/phút | 2 | 145 MiB | 8 | 0,14 s |
| 100 | 1 | 2+0 | 2,99 → 3,19 s (+6,4 %) | 88 / 159 s | 37/phút | 1 | 146 MiB | 7 | 0,66 s |
| 100 | 2 | 2+0 | 2,94 → 3,65 s (+24,2 %) | 50 / 87 s | 71/phút | 2 | 147 MiB | 8 | 1,15 s |
| 100 | 4 | 2+0 | 3,38 → 3,67 s (+8,4 %) | 29 / 48 s | 131/phút | 2 | 148 MiB | 8 | 0,66 s |
| 100 | 4 | 4+0 | 3,00 → 3,44 s (+14,7 %) | 29 / 47 s | 133/phút | 4 | 147 MiB | 10 | 0,47 s |
| 400 | 4 | 4+0 | 3,23 → 3,31 s (+2,4 %) | 96 / 171 s | 137/phút | 4 | 154 MiB | 10 | 0,79 s |
| 400 | 4 | **2+0** | 2,99 → 3,19 s (+6,9 %) | 97 / 173 s | 135/phút | 2 | 154 MiB | 8 | 0,72 s |

Mọi job đến hạn đều `delivered`, 0 lỗi chat, 0 transaction dài (lâu nhất 1,15 s khi CPU bão hòa; *idle in transaction* chỉ là trạng thái tức thời giữa hai câu lệnh trong transaction ngắn). Kết luận:

- Mỗi đơn vị concurrency xử lý ~35 job/phút với model 1,5 s; với gpt-6-luna thật (p50 2,7 s, p95 4,2 s — §10.3) ước ~20 job/phút.
- **Pool 2+0 đủ cho concurrency 4** (peak 2, không pool timeout): mỗi job chỉ giữ một kết nối trong các transaction ngắn và không giữ trong lúc gọi model. Tăng concurrency **không** cần tăng pool ⇒ không đụng ngân sách kết nối.
- Ảnh hưởng tới chat p95: 2,4 %–24 % trên máy dùng chung CPU (6/8 lần ≤ 10 %); dao động chủ yếu do tranh CPU của laptop (worker + API + PostgreSQL cùng máy). Trên EC2, service `proactive` bị giới hạn `cpus: 0.5` nên không thể chiếm CPU của API.
- Đề xuất: beta `PROACTIVE_WORKER_CONCURRENCY=2` (≈ 40 lời/phút với model thật: 400 lời hỏi thăm cùng 07:30 giao xong ~10 phút, trong grace 90 phút); tăng 4 khi cùng một mốc giờ có > 500 lịch. Giữ pool 2+0. RAM: đỉnh 154 MiB ⇒ `mem_limit 384m` dư; có thể hạ 320m.

### 10.2 Hạ tầng thật (chỉ đọc)

| Mục | Số liệu | Nguồn |
| --- | --- | --- |
| EC2 `moodprint-staging` | `t3.small` (2 vCPU, 2 GiB), `ap-southeast-2b`, credit `unlimited`, gp3 30 GiB/3000 IOPS, Ubuntu 24.04, SSM Online | `aws ec2 describe-*` |
| CPU 7 ngày | trung bình ngày 1,8–3,0 %, max ngày 4–17 %; p95 3,1 %, p99 4,1 %; `CPUCreditBalance` 576 (đầy), `CPUSurplusCreditsCharged` 0 | CloudWatch |
| RAM | **Không có số đo**: không có namespace `CWAgent`, không có log group CloudWatch | CloudWatch |
| Compose hiện tại | api `768m`/1,5 CPU, web `256m`/0,5 CPU ⇒ + proactive `384m` = 1.408 MiB giới hạn trên 2 GiB máy (còn ~600 MiB cho OS/Docker) | `deploy/compose.staging.yml` |
| Credit/chi phí | Gói Free ACTIVE, còn **95 USD** credit, hết hạn **09/04/2027**; tháng 10/2026 dùng 4,74 USD, credit bù 4,74 USD | Cost Explorer, Free Tier API |
| Supabase | Hosted `0019_journal`, `max_connections 60`, `moodprint_backend` limit 20, `idle_in_transaction_session_timeout 0`, `statement_timeout 120 s`; lúc đo 19 kết nối tổng, 5 của backend (4 idle, 1 idle-in-tx 0,1 s tức thời) | Supabase MCP, chỉ metadata |

Khuyến nghị: (1) cài CloudWatch agent (`deploy/aws/cloudwatch-agent.json` đã có) để có `mem_used_percent` 7 ngày trước khi bật worker; nếu p95 + 384 MiB > 70 % RAM → nâng `t3.medium` (4 GiB). (2) S1 Supabase (connection limit 30 + idle-tx 60 s) trước khi bật worker như 96 §5. CPU không phải ràng buộc (p95 3 %).

### 10.3 Chi phí model thật

gpt-6-luna (giá chuẩn đã kiểm trên trang pricing chính thức 31/10/2026: 0,10 / 0,01 cached / 0,50 USD mỗi 1M token): trung bình **1.651 input + 160 output token** mỗi lời hỏi thăm (91 lời sinh thật ở vòng eval 1, kể cả reasoning token) ⇒ ≈ **0,00025 USD/lời**. 100 người × 4 lời/ngày ≈ 0,10 USD/ngày (≈ 3 USD/tháng); 1.000 người ≈ 30 USD/tháng. Độ trễ model (thật): p50 2,7 s, p95 4,2 s.
