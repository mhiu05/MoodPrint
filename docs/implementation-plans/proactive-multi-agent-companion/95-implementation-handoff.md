# 95 — Bàn giao triển khai

## 1. Thứ tự đọc

1. [00-executive-summary.md](00-executive-summary.md)
2. [01-current-codebase-audit.md](01-current-codebase-audit.md) — dữ kiện, số dòng, ràng buộc
3. [03-architecture-decisions.md](03-architecture-decisions.md) — ADR-01…ADR-12
4. Phase 1: [01](phase-1/01-product-requirements.md) → [02](phase-1/02-multi-message-contract.md) → [03](phase-1/03-proactive-scheduler-and-workers.md) → [04](phase-1/04-database-and-migrations.md) → [05](phase-1/05-backend-api-and-agent-runtime.md) → [06](phase-1/06-frontend-ux-and-notifications.md) → [07](phase-1/07-persona-behaviors-and-prompts.md) → **[08 kế hoạch](phase-1/08-implementation-plan.md)** → [09](phase-1/09-testing-and-acceptance.md)
5. Cross-phase: [90](90-security-privacy-threat-model.md), [91](91-performance-cost-and-capacity.md), [92](92-visual-qa-and-agent-browser.md), [93](93-release-rollback-and-observability.md), [94](94-dependencies-risks-and-open-decisions.md)
6. Phase 2 (chỉ sau Gate G1): [phase-2/01](phase-2/01-product-requirements.md) … [phase-2/07](phase-2/07-testing-and-acceptance.md)

## 2. Thứ tự triển khai

```text
P1-00 baseline
 → Schema:      P1-01 (M-P1-A) → P1-02 (M-P1-B + inventory) → P1-03 (compat R0, rehearsal)
 → Multi-message: P1-04 → P1-05 → P1-06 → P1-07, P1-08            ⇒ Gate G1a
 → Proactive:   P1-09 → P1-10 → P1-11 → P1-12 → P1-13 → P1-14 → P1-15
 → UI:          P1-16, P1-17
 → Chất lượng:  P1-18, P1-19 → P1-20                                ⇒ Gate G1 → G2-entry
 → Phase 2:     P2-00 … P2-10                                        ⇒ Gate G2
```

Track multi-message (P1-04…P1-08) và track proactive (P1-09…P1-15) có thể song song sau P1-02, trừ P1-14 cần P1-05.

## 3. Đánh giá sẵn sàng

| Phase | Trạng thái | Bằng chứng | Điều kiện còn lại |
| --- | --- | --- | --- |
| **Phase 1** | **`CONDITIONALLY_READY`** | Mọi lead đã xác minh với mã nguồn ([01 §2](01-current-codebase-audit.md)); ADR có mặc định cho mọi quyết định quan trọng; 21 task có đủ 13 trường, file và test cụ thể ([phase-1/08](phase-1/08-implementation-plan.md)); schema đối chiếu metadata hosted; không cần dependency mới | (a) Owner xác nhận OD-01…OD-06 (mặc định đã có — code có thể bắt đầu); (b) BLK-02: áp dụng 0020 hosted trước mọi migration/deploy hosted (không chặn code local); (c) BLK-01: kiểm CPU/RAM EC2 trước khi bật worker trên staging; (d) OD-04: duyệt văn bản consent trước khi bật cho người dùng thật |
| **Phase 2** | **`BLOCKED`** (theo cổng phụ thuộc, không phải do thiếu thiết kế) | Thiết kế đầy đủ ([phase-2/02](phase-2/02-orchestration-architecture.md)–[05](phase-2/05-backend-and-database-contracts.md)), 11 task ([phase-2/06](phase-2/06-implementation-plan.md)) | Cần Gate G1 + G2-entry: SSE v2, `ai_runs.origin`, `ai_message_sources` + revalidation, pipeline proactive phải tồn tại và xanh; owner duyệt OD-08…OD-10 |

## 4. Quy tắc bất biến cho người triển khai

- Không làm Phase 2 khi chưa có Gate G1.
- Không đổi prompt đã đóng băng (`instructions()`, `VERSIONS`); chỉ thêm lớp runtime mới.
- Không dùng `Agent.as_tool()` hay handoff (ADR-09).
- Không đưa transcript vào input lời hỏi thăm; không cấp tool cho run proactive/specialist.
- Không tạo tin `actor='self'` cho run proactive.
- Không log nội dung, `user_id`, giờ hẹn.
- Mọi bảng mới: RLS + grant runtime + guest `INVENTORY` + `process_deletions` + `docs/supabase/schema.md`.
- Mọi route/setting mới: `api-reference.md`/`configuration.md` (gate `check_docs.py`).
- Migration: expand-only, forward-only, offline SQL review; không bao giờ áp dụng hosted khi chưa được owner cho phép; không dùng MCP `apply_migration`.

## 5. Nhật ký review của bộ tài liệu (31/10/2026)

| Lượt | Phát hiện | Đã sửa ở |
| --- | --- | --- |
| 1 — Kỹ thuật | Regex `consumeAIEvents` từ chối `?protocol=2` | [phase-1/02 §4.3](phase-1/02-multi-message-contract.md) |
| 1 — Kỹ thuật | Lượt trả lời dùng tin proactive-journal phải ghi stamp `journal-turn-v1` **trước** khi gọi model; nêu giới hạn continuity một lượt | [phase-1/05 §4.2](phase-1/05-backend-api-and-agent-runtime.md), [ADR-08](03-architecture-decisions.md#adr-08--context-policy-cho-tin-chủ-động) |
| 1 — Kỹ thuật | SSE persistent poll DB với seq cố định 1–3 ⇒ event "consulting" Phase 2 không tới client; thay bằng danh sách event dựng xác định từ DB (≤ 5) | [phase-2/05 §3](phase-2/05-backend-and-database-contracts.md), [phase-2/04](phase-2/04-collaboration-ui-ux.md), [phase-2/06 P2-07](phase-2/06-implementation-plan.md) |
| 1 — Kỹ thuật | Tên unique mới trùng `uq_ai_messages_run_id` do naming convention | [phase-1/04 §3](phase-1/04-database-and-migrations.md) |
| 1 — Kỹ thuật | Marker release-hold không có trên nhánh này | [93](93-release-rollback-and-observability.md) |
| 2 — Privacy | `ageBand` nằm trong payload "dữ liệu" nhưng lại điều khiển chính sách → chuyển sang lớp instructions | [phase-1/07 §1–2](phase-1/07-persona-behaviors-and-prompts.md) |
| 2 — Privacy | Sheet "Vì sao?" hiển thị giá trị cụ thể trái với mặc định tối thiểu hóa | [phase-2/04 §4](phase-2/04-collaboration-ui-ux.md) |
| 3 — Độ tin cậy | `last_seen_at` có thể NULL với người dùng mới ⇒ bị bỏ qua sai; lịch không có settings | [phase-1/05 §2.3, §3](phase-1/05-backend-api-and-agent-runtime.md) |
| 3 — Độ tin cậy | Claim chưa thể hiện "1 job running / user"; hoãn ở E5 không được trừ attempts | [phase-1/03 §5–6](phase-1/03-proactive-scheduler-and-workers.md) |
| 3 — Độ tin cậy | Run con Phase 2 không có `ai_turns` ⇒ cần accounting để phục hồi | [phase-2/05 §7](phase-2/05-backend-and-database-contracts.md) |
| 4 — UX/test | Khung tối tới 22:30 xung đột giờ yên lặng mặc định 22:00 | [phase-1/06 §3.2](phase-1/06-frontend-ux-and-notifications.md) |
| 4 — UX/test | "Tạm dừng đến khi bật lại" không có trạng thái biểu diễn được | [phase-1/06 §3.2](phase-1/06-frontend-ux-and-notifications.md) |
| 4 — UX/test | Animation trì hoãn nội dung trái DESIGN.md | [phase-1/02 §9](phase-1/02-multi-message-contract.md) |
| 4 — Phạm vi | Không có nội dung Phase 3; ma trận E2E phủ đủ 18 tình huống bắt buộc (E2E-01…E2E-20) | [92 §4](92-visual-qa-and-agent-browser.md) |

Không có test nào được chạy cho tính năng (chưa tồn tại). Lệnh đã chạy thật trong phiên: `python scripts/check_docs.py` (PASS), truy vấn metadata/aggregate Supabase (chỉ đọc), agent-browser baseline với dữ liệu tổng hợp.

## 6. Prompt cho coding agent — **chỉ Phase 1** (không thực thi trong phiên lập kế hoạch)

```text
VAI TRÒ: Bạn là kỹ sư full-stack triển khai PHASE 1 (nhiều bubble, lời hỏi thăm sáng/tối, lịch do người dùng
cấu hình, thông báo trong ứng dụng) cho MoodPrint. Không làm Phase 2.

NGUỒN SỰ THẬT (đọc theo thứ tự, không thiết kế lại):
docs/implementation-plans/proactive-multi-agent-companion/95-implementation-handoff.md §1, rồi
00, 01, 03, phase-1/01…09, 90, 91, 92, 93, 94. Kế hoạch thực thi: phase-1/08-implementation-plan.md.
Nếu mã nguồn khác với tài liệu (số dòng, tên hàm), tin mã nguồn, ghi chênh lệch vào sổ, giữ nguyên ý đồ thiết kế.

NHÁNH VÀ AN TOÀN:
- Tạo nhánh tính năng từ nhánh đích đã được owner chỉ định (mặc định: test/local-2026-10-30 sau khi owner xác nhận);
  dùng git worktree riêng. Không làm trên main. Không push, không mở PR, không merge, không deploy, không đổi AWS.
- Không chạm thay đổi chưa commit của người khác (công việc friendship-profile ở social/*, openapi.json, schema.d.ts).
- Không đổi dependency hay lockfile.
- backend/.env trỏ vào Supabase hosted: KHÔNG để nó điều khiển pytest/Alembic. Dùng PostgreSQL disposable local
  (DB tên kết thúc _test), luôn truyền DATABASE_MIGRATION_URL local. Không tạo role cluster-wide mà không xóa sau.
- Không áp dụng migration lên hosted. Chỉ tạo offline SQL (alembic upgrade --sql) để review.
- Không gửi tin thật, không bật scheduler ngoài môi trường test, không dùng dữ liệu thật.

CÁCH LÀM:
- Làm đúng thứ tự task P1-00 → P1-20 và đồ thị phụ thuộc ở phase-1/08 §1. Mỗi task: viết test đỏ trước, code tối
  thiểu, test xanh, rồi ruff/mypy (backend) hoặc npm run typecheck && npm test (frontend), và
  python scripts/check_docs.py khi đụng API/settings/bảng.
- Ghi sổ tiến độ docs/implementation-plans/proactive-multi-agent-companion/evidence/execution.md: task, commit,
  lệnh đã chạy, số pass/fail thật, chênh lệch so với tài liệu. Commit nhỏ theo task.
- Mọi cờ mới mặc định tắt: AI_MULTI_MESSAGE_ENABLED, PROACTIVE_ENABLED, PROACTIVE_WORKER_ENABLED.

RÀNG BUỘC THIẾT KẾ KHÔNG ĐƯỢC VI PHẠM:
- ai_messages unique (run_id, actor, part_index) đặt tên tường minh uq_ai_messages_run_part; version == max(sequence).
- SSE: v1 mặc định (ghép bubble, ≤6000 ký tự), v2 qua ?protocol=2; persistent replay vẫn seq 1–3.
- Không hiển thị bubble nào trước event completed; lưu mọi bubble trong một transaction.
- Run chủ động: ai_runs.origin='proactive', ai_turns.session_id NULL, không tin actor='self', không tool,
  không transcript trong input, Runner.run riêng, tracing tắt, store=False.
- authorize_proactive ở E1 và E5 dưới owner lock; thứ tự khóa users → ai_proactive_jobs → ai_conversations.
- Nhịp chỉ đọc entry saved của hôm qua (múi giờ lịch), tối đa 3, trong cửa sổ 90 ngày, khi journal_context_enabled;
  ghi ai_message_sources; tin proactive-journal chỉ vào context lượt sau nếu revalidate thành công.
- Quota/rate/concurrency người dùng chỉ đếm origin='user'; ngân sách chung vẫn tính mọi origin.
- Cầu Nối chỉ khi adult + MATCH + không bị hạn chế; không tên người, không lời mời.
- Distress screen xác định → mẫu tin an toàn, không gọi model, không trích nhật ký.
- UI tiếng Việt tự nhiên; không dùng "cron", "worker", "agent run", "SSE", "handoff", "embedding".
- Sửa nhãn "Today"/"Yesterday" thành "Hôm nay"/"Hôm qua".

CỔNG:
- Dừng ở Gate G1a (sau P1-08) để báo cáo; tiếp tục khi được xác nhận.
- Dừng ở Gate G1 (sau P1-20): báo cáo kết quả test thật, load test, eval (hoặc ghi rõ chưa chạy live), chênh lệch,
  rủi ro còn lại. Không bắt đầu Phase 2.

DỪNG VÀ HỎI khi: cần credential/đăng nhập; cần áp dụng gì lên hosted/AWS; test có sẵn fail không liên quan mà chặn
tiến độ; tài liệu mâu thuẫn với mã nguồn theo cách thay đổi thiết kế; cần quyết định OD-01…OD-07 khác mặc định.

KHÔNG tuyên bố test đã chạy nếu chưa chạy. Báo cáo cuối liệt kê mọi lệnh và kết quả thật.
```
