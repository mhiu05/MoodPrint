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
