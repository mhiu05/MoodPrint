# 93 — Phát hành, rollback và quan sát

Phiên lập kế hoạch **không** deploy, không đổi AWS, không áp dụng migration. Tài liệu này là quy trình cho người triển khai, dựa trên cơ chế đã có: image GHCR digest-pinned + attestation, poller EC2 5 phút, `deploy.sh` khôi phục cặp image cũ khi health fail ([deploy/aws/README.md](../../../deploy/aws/README.md)). Lưu ý: marker `deploy/guest-experience.release-hold` **không có** trên nhánh `test/local-2026-10-30`; theo ghi chú dự án ngày 29/10 nó nằm trên `main` và chặn publish staging cho tới khi owner gỡ bằng PR — phải kiểm lại trên nhánh tích hợp trước bước 1 dưới đây.

## 1. Cờ tính năng (mặc định tắt)

| Cờ | Phase | Tác dụng khi bật | Kill switch |
| --- | --- | --- | --- |
| `AI_MULTI_MESSAGE_ENABLED` | 1 | Model trả 1–4 bubble | Tắt → 1 bubble, lịch sử giữ nguyên |
| `PROACTIVE_ENABLED` | 1 | API lịch/inbox + UI | Tắt → UI ẩn, GET `available=false`, ghi 503 |
| `PROACTIVE_WORKER_ENABLED` | 1 | Vòng lặp giao tin | Tắt → không giao; job đến hạn sau đó thành `missed_window` |
| `PROACTIVE_ROLLOUT_USER_IDS` | 1 | Giới hạn nhóm thử | Đặt rỗng/1 user |
| `AI_COLLABORATION_ENABLED` | 2 | Coordinator chạy | Tắt → primary một mình |

Đổi cờ = cập nhật SecureString runtime (`/moodprint/staging/runtime`) và redeploy cặp image hiện tại; không cần build mới.

## 2. Trình tự phát hành Phase 1

| Bước | Hành động | Kiểm tra trước khi sang bước sau |
| --- | --- | --- |
| 0 | Owner duyệt & áp dụng `0020` hosted (đang thiếu) | Readiness của image hiện tại vẫn 200 |
| 1 | Release **R0** (compat): `READY_REVISIONS` chấp nhận 0020/0021/0022, không code tính năng | CI xanh; staging ready |
| 2 | Rehearsal M-P1-A/B trên `*_test` khôi phục từ dump schema hosted | Báo cáo PASS, sha256 |
| 3 | Owner duyệt → áp dụng M-P1-A/B hosted bằng offline SQL đã review (một transaction, backup trước) | `alembic_version = 0022`; R0 ready |
| 4 | Release **R1**: code Phase 1, mọi cờ tắt | Regression: hành vi giống R0 |
| 5 | Bật `AI_MULTI_MESSAGE_ENABLED` trên staging | Gate G1a; 48 giờ không lỗi `INVALID_AI_EVENT` |
| 6 | Bật `PROACTIVE_ENABLED` + `PROACTIVE_ROLLOUT_USER_IDS` = tài khoản thử nghiệm đã đồng ý | UI lịch hoạt động |
| 7 | Bật `PROACTIVE_WORKER_ENABLED` | 7 ngày: 0 giao trùng, 0 ngoài giờ, lag p95 ≤ 10 phút |
| 8 | Mở rollout (xóa allowlist) — chỉ sau Gate G1 và owner đồng ý | — |

Phase 2: R2 compat chấp nhận 0022/0023 → áp dụng M-P2-A → R3 code cờ tắt → bật `AI_COLLABORATION_ENABLED` cho allowlist → Gate G2.

## 3. Ma trận rollback

| Tình huống | Hành động | Dữ liệu |
| --- | --- | --- |
| Lỗi hiển thị nhiều bubble | Tắt `AI_MULTI_MESSAGE_ENABLED` | Tin nhiều bubble cũ vẫn hiển thị đúng (R1 đọc được) |
| Giao sai giờ/trùng | Tắt `PROACTIVE_WORKER_ENABLED` ngay | Job còn lại hết hạn → `missed_window` |
| Lỗi API lịch | Tắt `PROACTIVE_ENABLED` | Lịch giữ nguyên trong DB |
| Lỗi nghiêm trọng R1 | Poller/SSM chuyển về cặp image R0 | R0 chấp nhận 0022, bỏ qua bảng mới |
| Lỗi migration khi áp dụng | Transaction rollback tự động (một transaction) | Không đổi |
| Cần gỡ hẳn schema | **Không** rollback schema; migration forward đã review để drop bảng mới khi cờ tắt và owner đồng ý | — |
| Cộng tác sai | Tắt `AI_COLLABORATION_ENABLED` | Receipt giữ cho điều tra 90 ngày |

## 4. Metric (log `metric=…`, content-free)

| Metric | Loại | Nguồn |
| --- | --- | --- |
| `proactive_job_state` (state, reason, bot, slot) | Counter | Worker |
| `proactive_lag_seconds` | Gauge/histogram | Publish |
| `proactive_queue_due` | Gauge, mỗi 60 s | Tick |
| `proactive_tick_ms` | Gauge | Tick |
| `proactive_budget_skip` | Counter | E1 |
| `proactive_safety_template` | Counter | Executor |
| `ai_events_protocol` (v1/v2) | Counter | SSE route |
| `ai_reply_parts` (1–4) | Counter | Runtime |
| `collaboration_state` (edge, rule, status, reason) | Counter | Coordinator |
| `collaboration_duration_ms` | Histogram | Coordinator |

CloudWatch metric filter trên log group `/moodprint/staging/containers` (như các metric hiện có trong [cloudwatch-alarms.json](../../../deploy/aws/cloudwatch-alarms.json)).

## 5. Alarm đề xuất

| Alarm | Điều kiện | Hành động |
| --- | --- | --- |
| `ProactiveFailedHigh` | `state=failed` ≥ 5 trong 15 phút | Kiểm provider/validator; cân nhắc tắt worker |
| `ProactiveLagHigh` | `proactive_lag_seconds` p95 > 900 trong 30 phút | Tăng `PROACTIVE_WORKER_CONCURRENCY` hoặc kiểm DB |
| `ProactiveQueueStuck` | `proactive_queue_due` > 50 trong 3 lần liên tiếp | Kiểm worker còn chạy, lease |
| `ProactiveBudgetSkip` | ≥ 1 trong 1 giờ | Xem ngân sách ngày |
| `CollaborationTimeoutHigh` | `status=timeout` / tổng > 10 % trong 1 giờ | Giảm cạnh/tắt cờ |
| `AiBudget80` (đã có) | Không đổi | Đã bao gồm chi phí proactive/collab |

## 6. Runbook

### 6.1 "Tôi nhận lời hỏi thăm hai lần"
1. Tìm job theo `job_id` từ log quanh giờ đó (không dùng nội dung).
2. Kiểm unique `(user_id, bot_id, slot, local_date)` — hai job khác `local_date`? → kiểm timezone đã đổi.
3. Nếu cùng job có hai run `origin=proactive` → lỗi P0: tắt worker, mở sự cố.

### 6.2 "Lời hỏi thăm đến lúc nửa đêm"
1. So `due_at` với `ai_proactive_settings.timezone` và `local_time`.
2. Kiểm `tzdata` và lần đổi timezone gần nhất (`settings.version`).
3. Tắt worker nếu nhiều người bị.

### 6.3 Queue kẹt
1. `SELECT status, count(*) FROM moodprint.ai_proactive_jobs WHERE available_at <= now() GROUP BY 1` (metadata).
2. `running` với `lease_until` quá hạn → tick kế tiếp sẽ reclaim; nếu không: kiểm vòng lặp lifespan có chạy (`proactive_tick_ms` vắng mặt).
3. Kiểm kết nối *idle in transaction* (đã thấy 3 kết nối ~8 phút khi kiểm, [01 §12](01-current-codebase-audit.md)).

### 6.4 Provider ngừng
Job tự `retry` tới hết hạn rồi `skipped(expired)`; không cần thao tác. Không gửi bù sau khi provider hồi phục.

## 7. Cấu hình và secrets

Không có secret mới. Biến mới ([phase-1/05 §8](phase-1/05-backend-api-and-agent-runtime.md), [phase-2/05 §7](phase-2/05-backend-and-database-contracts.md)) được thêm vào SecureString runtime hiện có và `backend/.env.example` (giá trị mặc định tắt). Production validator chặn bật worker khi thiếu accounting/budget.

## 8. Tài liệu vận hành cần cập nhật khi triển khai

[docs/backend/operations.md](../../backend/operations.md), [docs/backend/data-lifecycle.md](../../backend/data-lifecycle.md), [docs/agents/runtime.md](../../agents/runtime.md), [docs/agents/context-memory.md](../../agents/context-memory.md), [ARCHITECTURE.md](../../../ARCHITECTURE.md) (§5, §8: thêm worker proactive và topology).

## 9. Checklist sẵn sàng staging (Gate G1, cập nhật 31/10/2026)

Trạng thái: ☑ = đã có bằng chứng trong [evidence/execution.md](evidence/execution.md); ☐ = việc của owner/triển khai (không làm trong phiên code).

| # | Hạng mục | Trạng thái |
| --- | --- | --- |
| 1 | Mã P1-00…P1-20 trên `feat/proactive-companion-phase1`, mọi cờ mặc định tắt | ☑ |
| 2 | Backend suite, ruff, mypy, frontend unit/typecheck/build, E2E fixture, fullstack proactive xanh (trừ fail có sẵn đã phân loại) | ☑ |
| 3 | Offline SQL 0020→0022 rehearsal trên chuỗi sạch + role mirror | ☑ (P1-03) |
| 4 | Rehearsal trên bản sao `pg_dump --schema-only` của hosted (U-04) | ☐ owner cho phép dump |
| 5 | Hosted áp dụng 0020, rồi 0021+0022 qua `scripts/apply_supabase_review.py` (một transaction, có backup) | ☐ owner (BLK-02) |
| 6 | Rebase/tích hợp với nhánh friendship-profile của Codex (trùng `models.py`, `e2e_server.py`, `conftest.py`, `openapi.json`, `schema.d.ts`, readiness tests) và chạy lại toàn bộ suite | ☐ |
| 7 | Supabase S1: `ALTER ROLE moodprint_backend CONNECTION LIMIT 30; ALTER ROLE moodprint_backend SET idle_in_transaction_session_timeout = '60s';` | ☐ owner |
| 8 | CloudWatch agent bật ≥ 7 ngày, `mem_used_percent` p95 + 384 MiB < 70 % (nếu không: `t3.medium`) | ☐ owner |
| 9 | Áp dụng metric filter + alarm `Proactive*` từ `deploy/aws/cloudwatch-alarms.json` | ☐ owner |
| 10 | Env staging: `AI_ACCOUNTING_ENABLED=true`, `AI_DAILY_BUDGET_USD>0`, `PROACTIVE_ENABLED=true`, `PROACTIVE_ROLLOUT_USER_IDS=[≤5 tài khoản thử nghiệm đã đồng ý]`, service `proactive` `PROACTIVE_WORKER_ENABLED=true`, `PROACTIVE_WORKER_CONCURRENCY=2` | ☐ |
| 11 | 7 ngày staging: 0 giao trùng (`ai_proactive_jobs` delivered ↔ đúng 1 run), 0 giao trong giờ yên lặng, 0 rò rỉ (canary), lag p95 < 5 phút | ☐ |
| 12 | Owner ký checklist (G1 trong [phase-1/08 §3](phase-1/08-implementation-plan.md)) | ☐ |

**Rollback nhanh (theo thứ tự tác động tăng dần):** (a) `PROACTIVE_WORKER_ENABLED=false` + `docker compose up -d proactive` → không sinh lời mới; job đang chạy hết lease, không commit dở. (b) `PROACTIVE_ENABLED=false` → API/UI ẩn (GET `available=false`, ghi 503, inbox rỗng). (c) `AI_MULTI_MESSAGE_ENABLED=false` → trả lời một tin. (d) Image R1 → R0 (`release/proactive-r0-compat`, ready ở 0020/0021/0022). Không downgrade schema; bảng mới trống/không dùng không ảnh hưởng R0.

## 10. Phase 2 — phát hành và rollback

Trình tự bật, metric `collaboration_*`, alarm `CollaborationTimeouts`/`CollaborationFailures`, dừng khẩn cấp và rollback R2 → R1 ở [operations](../../backend/operations.md#trợ-lý-phối-hợp-phase-2). Điều kiện thêm cho rollback: image R1 phải chấp nhận cả `0022` và `0023` trước khi `0023` được áp dụng hosted (yêu cầu tích hợp, chưa làm trên nhánh Phase 1). Checklist owner chưa ký.
