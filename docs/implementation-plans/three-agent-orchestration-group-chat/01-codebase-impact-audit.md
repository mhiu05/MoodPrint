# 01 — Audit tác động mã nguồn (kiểm trên `c8c55f8`)

## Hiện trạng đã xác minh trong source

| Khu vực | Hiện trạng | Tác động V3 |
| --- | --- | --- |
| Registry | `app/ai/registry.py` 5 `BotPublicDTO`; `BotId = Literal[5 id]` (`app/contracts.py:10`) dùng ở schemas, proactive, collaboration, memory | Mở rộng `BotId` lên 8 id; registry 3 trợ lý + 5 legacy; `/bots` theo cờ A |
| Prompt | `prompts.py`: `instructions()` khóa byte cho eval (legacy/A/B), `CONVERSATIONAL_PERSONAS`, `PROACTIVE_PERSONAS[(bot,slot)]` | Thêm persona 3 trợ lý (mới, hợp nhất), không sửa text cũ |
| Năng lực theo tên bot | `runtime.tools()` rẽ nhánh `bot_id=='nhip'/'guong'/'may'`; `provider._stream` `journal_mode = bot_id=='nhip'`; `chat_routes` mood scope chỉ `nhip`; `conversation_intent` mặc định theo bot; `evidence.source_instructions`; `MEMORY_BOTS` | Thay bằng bảng năng lực (`journal`, `mood_scope`, `memory`, `challenges`) cho cả bot cũ và mới |
| CHECK DB theo bot | `ai_conversations` (5 id), `ai_proactive_schedules/jobs` (5), `memory_proposals`, `memory_embeddings`, `memory_embedding_jobs` (4) | Migration 0024 mở rộng |
| Chat runtime | `runtime.drive`: khóa owner → chiếu ngữ cảnh (`model_messages`, stamp) → `consult` (Phase 2) → `provider.run_reply` → publish 1 giao dịch (bubbles + run completed + accounting) | Chèn `orchestrate` cho Điều phối; publish theo người nói thật |
| Phase 2 coordinator | Luật R1–R4 regex, 3 cạnh cố định (Mây/Gương/Rủ Rê ↔ Nhịp/Rủ Rê), 1 lời gọi specialist không tool, receipt `ai_collaborations` | Giữ nguyên cho trợ lý cũ khi cờ A tắt; V3 dùng `ai_orchestration_steps` mới |
| Usage | `ai_usage` 1 dòng/run, CHECK `requests_started ≤ 3`, `tool_calls ≤ 2` | Mỗi agent trong workflow có child run riêng ⇒ không cần nới CHECK |
| SSE | `/ai/runs/{id}/events` v1/v2; danh sách event của hội thoại đã lưu là hàm thuần của DB (`persistent_events`) | Thêm `speaker`, `steps`; endpoint SSE nhóm riêng |
| Proactive | `BOT_ORDER` 5 trợ lý; worker theo bảng job; Nhịp sáng đọc nhật ký hôm qua khi `journal_context_enabled` | Thêm 3 trợ lý; lịch cũ bị bỏ qua khi cờ A bật, chuyển rõ ràng |
| Xóa dữ liệu | `purge_proactive` + xóa `ai_conversations` (cascade tin) + guest `INVENTORY` | Thêm bảng mới |
| Frontend | `RealApp.tsx` 2187 dòng (Assistants + ConversationBody); `companions/registry.ts` 5 bot; `stream.ts` validate v2 chặt | Thêm 3 avatar, tách nhóm vào `features/real/groups/` |
| SDK | `openai-agents==0.24.0`; mọi run dùng `Runner.run_streamed`; fake model của repo chỉ hỗ trợ streaming | Nested as_tool phải chạy streaming ⇒ luôn truyền `on_stream` |

## Lệch tài liệu ↔ source (đã ghi)

1. Phase 2 docs mô tả `Runner.run` cho specialist; source dùng `Runner.run_streamed` (`max_turns=1`) — đã ghi D-04 trong sổ Phase 2, đúng với source.
2. Phase 2 docs nói đủ tuổi AI 16+; source chỉ cho 18+ (`collaboration/eligibility.py`) — đúng quy tắc sản phẩm hiện tại. V3 dùng cùng một hàm.
3. Chuỗi migration thực tế: `0019_journal → 0020_private_profile_retirement → 0021_multi_message → 0022_proactive_messages → 0023_collaboration` (khớp đề bài). V3 thêm `0024_three_agent_groups`.

## Baseline

Kết quả baseline `pytest` trên bản tách rời `c8c55f8`: xem [12](12-execution-evidence.md).
