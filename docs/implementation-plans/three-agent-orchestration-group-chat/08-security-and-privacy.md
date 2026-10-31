# 08 — Bảo mật và quyền riêng tư (mô hình mối đe dọa)

| # | Mối đe dọa | Kiểm soát (trong code, không chỉ prompt) | Test |
| --- | --- | --- | --- |
| T1 | Handoff mang lịch sử riêng tư sang chuyên gia | `input_filter` **dựng lại** input = bối cảnh chuyển lượt có kiểu + tin mới nhất; `pre_handoff_items`, `new_items`, `input_items` rỗng; không dùng server-managed conversation (`store=False`) | `test_orchestration_handoff` (model giả ghi lại input thật) |
| T2 | `as_tool` chuyển transcript/ghi nhớ | Nested run chỉ nhận item do `input_builder` dựng từ tham số đã validate + dữ liệu đã cấp; `previous_response_id`/`session` None | `test_orchestration_sdk` |
| T3 | Prompt injection qua nhật ký | Nhật ký chỉ đi vào run Nhật ký dưới nhãn dữ liệu; output có kiểu, validator chặn ID ngoài tập cấp, URL, chẩn đoán, chép nguyên văn ≥ 9 từ; Điều phối nhận JSON đã kiểm, không ID | test injection |
| T4 | Model tự cấp quyền/ủy quyền | Plan schema đóng (không trường quyền); `policy.validate` dùng grants đọc dưới khóa owner; `is_enabled` theo decision; wrapper mở bước kiểm lại (#1), hook trước mỗi request (#2), publish (#3) | `test_orchestration_policy`, `test_orchestration_sdk` |
| T5 | Thu hồi giữa lượt | Monitor 0,5 s (Phase 1) + #2/#3; bước mở bị đóng `cancelled`; không publish | test revoke |
| T6 | Bịa cộng tác | Dòng "đã hỏi ý" / người nói chỉ từ receipt `completed ∧ used_in_reply` và `ai_runs.bot_id` của run mang bubble | test receipts |
| T7 | Nhóm của người khác | Mọi truy vấn nhóm lọc `user_id` + `kind='group'`; 404 đồng nhất | `test_groups_api` |
| T8 | Thành viên bị bỏ vẫn nói | Bỏ thành viên hủy lượt chạy; publish kiểm `status='active'` trong cùng giao dịch | `test_groups_turn` |
| T9 | Thêm thành viên lộ lịch sử | `history_from_sequence` mặc định = phiên bản hiện tại; chia sẻ lịch sử phải chọn rõ | `test_groups_api` |
| T10 | Nhóm thành đường vòng qua quyền nhật ký | Nhật ký trong nhóm chỉ có tool nhật ký khi `journal_access` của nhóm bật; lượt đọc nhật ký ký `journal-turn-v1` | `test_groups_turn` |
| T11 | Đệ quy / chi phí mất kiểm soát | Độ sâu 1 (chuyên gia không có tool gọi trợ lý), ≤ 2 chuyên gia, `WorkflowBudget` ≤ 7 lời gọi, per-run ≤ 3/2 (CHECK `ai_usage`), hạn mức ngày, chia sẻ ngân sách, timeout | test limits |
| T12 | Log/trace lộ nội dung | `tracing_disabled`, `trace_include_sensitive_data=False`; log chỉ enum/số; receipt chỉ digest | test log |
| T13 | SSE lộ dữ liệu | Event chỉ chứa bubble đã commit + enum người nói/bước; không token tạm | `test_orchestration_sse`, `test_groups_sse` |
| T14 | Xóa tài khoản / guest hết hạn | `purge_proactive` xóa receipts + thành viên; guest `INVENTORY`; guest không được điều phối/nhóm | `test_v3_migration`, guest inventory test |
| T15 | Quyền cũ (stale) | Mỗi cạnh có `version`; receipt ghi version lúc mở, so ở #2/#3 | test revoke |
| T16 | 18+ | Điều phối/nhóm chỉ cho `collaboration_eligible` (18+, đã đăng ký, không bị khóa) — một hàm để đổi sang `is_adult_eligible()` khi tích hợp Codex | test eligibility |

Không có kiểm soát nào chỉ nằm trong system prompt. Prompt là lớp thứ hai.
