# V3 — Ba trợ lý, điều phối thông minh và trò chuyện nhóm

Nhánh `feat/three-agent-smart-orchestration-group-chat`, worktree `E:\MoodPrint-agent-platform-v3`, tách từ `feat/proactive-companion-phase2@c8c55f8` (HEAD đã kiểm, cây sạch). Không push, không merge, không deploy.

## Ba mục tiêu

| Mục tiêu | Cờ (mặc định OFF) | Tài liệu |
| --- | --- | --- |
| A. Thay 5 trợ lý mặc định bằng **Điều phối, Nhật ký, Hoạt động** | `AI_THREE_AGENT_EXPERIENCE_ENABLED` | [02](02-three-agent-product-spec.md) |
| B. Điều phối thông minh: planner LLM + policy backend + `Agent.as_tool()` + SDK `handoff` thật | `AI_SMART_ORCHESTRATION_ENABLED` | [03](03-smart-orchestration-architecture.md), [04](04-as-tool-and-handoff-contracts.md) |
| C. Nhóm AI nhiều trợ lý (một người dùng + 2–3 trợ lý) | `AI_GROUP_CHAT_ENABLED` | [05](05-group-chat-product-spec.md), [06](06-group-chat-backend-and-database.md) |

Cờ B và C chỉ có tác dụng khi A bật. Khi cả ba tắt, hành vi Phase 1/Phase 2 được giữ nguyên (5 trợ lý, R1–R4, SSE v1/v2).

## Nguyên tắc xuyên suốt

1. **Quyền do backend quyết.** LLM chỉ *đề xuất* (planner, chọn người nói, gọi tool/handoff); mọi đề xuất qua policy thuần (`app/ai/orchestration/policy.py`) dùng trạng thái quyền đọc dưới khóa owner. Không trường nào trong output model được coi là quyền.
2. **Chỉ ghi điều đã thật sự chạy.** Mỗi bước (plan, consult, handoff, phát biểu trong nhóm) có một receipt không chứa nội dung trong `ai_orchestration_steps` và một child run (`ai_runs.origin='agent'`) mang usage thật. UI chỉ hiển thị phối hợp từ receipt `completed` + `used_in_reply`.
3. **Không giữ kết nối DB khi gọi model.** Giao dịch ngắn: mở bước (khóa owner) → gọi model (không kết nối) → đóng bước / publish (khóa owner, kiểm quyền lần cuối).
4. **Không gộp lịch sử riêng tư.** Hội thoại cũ của Mây/Gương/Nhịp/Rủ Rê/Cầu Nối giữ nguyên, chỉ đọc; lịch hỏi thăm cũ được giữ và chỉ chuyển khi người dùng chọn.
5. **Nhật ký không rời khỏi Nhật ký.** Trợ lý khác chỉ nhận tóm tắt có kiểu, không trích dẫn, và chỉ khi người dùng bật quyền chia sẻ tương ứng.

## Bản đồ tài liệu

- [01](01-codebase-impact-audit.md) audit tác động mã nguồn (đã kiểm với source, có ghi lệch tài liệu)
- [02](02-three-agent-product-spec.md) đặc tả ba trợ lý, chuyển đổi từ năm trợ lý
- [03](03-smart-orchestration-architecture.md) kiến trúc điều phối lai (fast path / smart path / policy)
- [04](04-as-tool-and-handoff-contracts.md) hợp đồng `Agent.as_tool()` và handoff (SDK 0.24.0 đã kiểm mã)
- [05](05-group-chat-product-spec.md) đặc tả sản phẩm nhóm AI
- [06](06-group-chat-backend-and-database.md) API, schema, SSE nhóm
- [07](07-frontend-ux-spec.md) UX/UI
- [08](08-security-and-privacy.md) mô hình mối đe dọa
- [09](09-implementation-plan.md) kế hoạch, đồ thị phụ thuộc task, cổng A/B/C
- [10](10-testing-and-acceptance.md) kiểm thử và tiêu chí chấp nhận
- [11](11-migration-and-rollback.md) migration 0024, rollout và rollback
- [12](12-execution-evidence.md) sổ thực thi (kết quả lệnh thật)
