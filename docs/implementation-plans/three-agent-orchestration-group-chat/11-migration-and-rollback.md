# 11 — Migration, rollout và rollback

## Migration `0024_three_agent_groups`

Chuỗi đã kiểm: `0019_journal → 0020_private_profile_retirement → 0021_multi_message → 0022_proactive_messages → 0023_collaboration → 0024_three_agent_groups`. Chỉ mở rộng (xem [06](06-group-chat-backend-and-database.md) §2). Không ghi lại hàng nào; không có giá trị mặc định nào cấp quyền chia sẻ. `downgrade()` bị vô hiệu như các migration trước (chỉ forward).

`READY_REVISIONS = ("0024_three_agent_groups",)`: image V3 không nhận traffic trên schema cũ hơn (ORM ánh xạ `kind`, `active_agent*`, `mentions`).

## Thứ tự bật

1. Áp 0024 (offline SQL đã review, một transaction — như quy trình hosted hiện có). Image V3 với **cả ba cờ tắt** ⇒ hành vi Phase 2.
2. Bật `AI_THREE_AGENT_EXPERIENCE_ENABLED` cho cohort `AI_V3_ROLLOUT_USER_IDS`.
3. Bật `AI_SMART_ORCHESTRATION_ENABLED` (cần multi-message + accounting).
4. Bật `AI_GROUP_CHAT_ENABLED`.

## Rollback

| Mức | Hành động | Hệ quả |
| --- | --- | --- |
| R-C | Tắt `AI_GROUP_CHAT_ENABLED` | API nhóm trả 404/503; dữ liệu nhóm giữ nguyên, hết hạn theo retention |
| R-B | Tắt `AI_SMART_ORCHESTRATION_ENABLED` | Điều phối trả lời đơn; `active_agent` bị bỏ qua (lượt sau do Điều phối trả lời) |
| R-A | Tắt `AI_THREE_AGENT_EXPERIENCE_ENABLED` | 5 trợ lý cũ trả lời lại như Phase 2; hội thoại của 3 trợ lý mới vẫn đọc/xóa được nhưng không gửi được (`AGENT_UNAVAILABLE`); lịch cũ chạy lại; lịch của 3 trợ lý mới bỏ qua (`agent_unavailable`) |
| R-image | Quay về image Phase 2 | **Chỉ an toàn khi chưa có dữ liệu V3**: image Phase 2 validate `bot_id` theo 5 giá trị nên sẽ lỗi khi đọc hội thoại/lịch của trợ lý mới. Nếu đã có dữ liệu V3, dùng R-A (image V3, cờ tắt). Schema 0024 không cần hoàn tác (image Phase 2 vẫn chèn được hàng mới nhờ default) — phải mở rộng `READY_REVISIONS` của image Phase 2 để chấp nhận 0024 trước khi dùng nó |

## Tích hợp với nhánh Codex

Xem [12](12-execution-evidence.md) mục tích hợp.
