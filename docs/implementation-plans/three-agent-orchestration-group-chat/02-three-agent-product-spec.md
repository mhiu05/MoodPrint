# 02 — Ba trợ lý mặc định (Gate A)

## 1. Danh tính

| ID | Tên hiển thị | Vai trò (UI) | Mô tả ngắn | Avatar |
| --- | --- | --- | --- | --- |
| `dieuphoi` | Điều phối | Trò chuyện & lên hướng đi | Hiểu điều bạn cần, cùng bạn gỡ rối và gọi đúng người giúp. | La bàn tròn màu xanh rêu |
| `nhatky` | Nhật ký | Nhật ký & cảm xúc | Nhìn lại những gì bạn đã ghi, nhận ra điều lặp lại. | Cuốn sổ mở màu hổ phách |
| `hoatdong` | Hoạt động | Hoạt động & học hỏi | Biến ý định thành một việc nhỏ làm được ngay. | Ngôi sao nhảy màu san hô |

## 2. Trách nhiệm, công cụ, quyền

| | Điều phối | Nhật ký | Hoạt động |
| --- | --- | --- | --- |
| Thừa kế từ | Mây (đồng hành chung) + Gương (tự khám phá) | Nhịp (cảm xúc, thói quen, nhật ký, mood) | Rủ Rê (hoạt động, học, thử thách) |
| Tool 1:1 | `propose_memory` | `propose_memory`, `search_journal_entries`, `read_mood_summary` (chỉ khi người dùng chọn khoảng ngày) | — |
| Tool điều phối (cờ B) | `consult_nhatky`, `consult_hoatdong` (as_tool), `transfer_to_nhatky`, `transfer_to_hoatdong` (handoff) — chỉ khi policy cho phép | — | — |
| Đọc nhật ký | **Không** (kể cả khi điều phối); chỉ nhận tóm tắt có kiểu qua cạnh đã bật | Có, theo quyền như Nhịp | Không |
| Hỏi thăm định kỳ | sáng: lời chào + một câu hỏi tò mò nhẹ; tối: hỏi thăm, cho phép nghỉ | sáng: nhắc một điều đã ghi hôm qua (khi bật nhật ký cho lời hỏi thăm) + một việc nhỏ; tối: mời ghi lại | sáng/tối: một thử thách ≤ 10 phút (tránh loại đã dùng) |

Persona (prompt mới trong `app/ai/prompts.py`, không sửa văn bản cũ):

- **Điều phối**: tự nhiên, ấm, gọn; xác định điều người dùng thật sự muốn; chia nhỏ việc; khi có tóm tắt từ chuyên gia thì hợp nhất thành một câu trả lời, phân biệt điều người dùng đã ghi với suy luận; không nói về "công cụ", "agent", "handoff"; không đoán cảm xúc khi không có căn cứ; không trị liệu/chẩn đoán.
- **Nhật ký**: điềm tĩnh, rõ; chỉ dựa trên bằng chứng được cấp trong lượt; tách "bạn đã ghi" khỏi "mình đoán"; không chẩn đoán; không bịa trích dẫn; ngày thiếu là chưa có dữ liệu.
- **Hoạt động**: lanh lợi, khích lệ, không thúc ép; một ý cụ thể bắt đầu được ngay theo thời gian/năng lượng/dụng cụ; không đặt chỗ, gửi tin hay liên hệ ai.

## 3. Chuyển đổi từ năm trợ lý

| Cũ | Sang | Cách xử lý dữ liệu |
| --- | --- | --- |
| Mây, Gương | Điều phối | Hội thoại cũ giữ nguyên dưới bot cũ, nhãn "Cuộc trò chuyện cũ", chỉ đọc (đọc, đổi tên, tải xuống, xóa). Ghi nhớ đã duyệt của Mây/Gương **không** tự chuyển sang Điều phối. |
| Nhịp | Nhật ký | Như trên. Lịch hỏi thăm của Nhịp: tạm dừng (không xóa) khi cờ A bật; người dùng bấm "Chuyển sang Nhật ký" để tạo lịch tương đương. |
| Rủ Rê | Hoạt động | Như trên; lịch chuyển rõ ràng sang Hoạt động. |
| Cầu Nối | (không có) | Tìm bạn là tính năng riêng (`/connect`). Lịch Cầu Nối tạm dừng, chỉ có thể tắt; không chuyển sang trợ lý nào. |

Chuyển lịch (`POST /ai/proactive/schedules/{bot}/{slot}/migrate {target, expectedVersion}`) chỉ cho cặp trong bảng; tạo lịch mới cùng giờ/ngày/trạng thái bật, tắt lịch cũ (giữ hàng), trong một giao dịch; nếu hôm nay lịch cũ đã có job, lịch mới bắt đầu từ ngày mai (không trùng). Không mở rộng quyền: Nhật ký sáng chỉ đọc nhật ký khi `journal_context_enabled` như Nhịp.

## 4. Hành vi theo cờ

| | Cờ A tắt (mặc định) | Cờ A bật |
| --- | --- | --- |
| `GET /bots` | 5 trợ lý cũ (byte như Phase 2) | đúng 3 trợ lý |
| `GET /bots/legacy` | `[]` | 5 trợ lý cũ, `legacy=true`, `replacedBy` |
| Tạo hội thoại bot cũ | như Phase 2 | 409 `LEGACY_COMPANION` |
| Tạo hội thoại bot mới | 409 `AGENT_UNAVAILABLE` | được |
| Gửi tin hội thoại cũ | như Phase 2 | 409 `LEGACY_CONVERSATION` |
| Gửi tin hội thoại bot mới (dữ liệu có từ lúc bật) | 409 `AGENT_UNAVAILABLE` (đọc/xóa vẫn được) | được |
| Lịch hỏi thăm cũ | chạy như Phase 2 | được giữ, bỏ qua với `skip_reason='legacy_companion'` |

18+: ba trợ lý dùng cùng cổng AI hiện có (`assert_purpose(AI)`, đủ tuổi); điều phối/nhóm chỉ cho tài khoản đã đăng ký và `collaboration_eligible` (18+), hàm duy nhất cần đổi sang `is_adult_eligible()` của Codex khi tích hợp.
