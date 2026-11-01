# 05 — Nhóm AI: đặc tả sản phẩm (Gate C)

Một nhóm = **một người dùng + 2–3 trong ba trợ lý** (Điều phối, Nhật ký, Hoạt động). Không có người dùng thứ hai, không có trợ lý tự tạo, không có trợ lý cũ.

## Hành động của người dùng

| Hành động | Quy tắc |
| --- | --- |
| Tạo nhóm | Tên (1–60 ký tự, mặc định gợi ý theo thành viên) + chọn ít nhất 2 trợ lý. Nhóm xuất hiện trong danh sách hội thoại. |
| Mở lại | Từ mục "Nhóm" trên trang Trợ lý; lịch sử phân trang như chat 1:1. |
| Đổi tên | Chủ nhóm; không gửi tới trợ lý. |
| Thêm trợ lý | Chỉ trợ lý V3 chưa là thành viên; chọn rõ "chia sẻ lịch sử trước đó" hay "chỉ từ bây giờ" (mặc định: chỉ từ bây giờ). |
| Bỏ trợ lý | Không xuống dưới 2; lượt đang chạy bị dừng; trợ lý không nhận tin mới; tin cũ giữ tên người nói. |
| Cho Nhật ký dùng nhật ký trong nhóm | Công tắc riêng mỗi nhóm, mặc định tắt; giải thích rằng câu trả lời của Nhật ký sẽ hiển thị cho các trợ lý khác trong nhóm. |
| Xóa nhóm | Xóa tin nhắn và thành viên; không thể hoàn tác. |

## Ai trả lời

- `@Điều phối`, `@Nhật ký`, `@Hoạt động`: đúng trợ lý đó (theo thứ tự nhắc). `@mọi người`: tất cả thành viên (tối đa 3), Điều phối nói cuối để gom ý.
- Không nhắc ai: tin chào hỏi/ngắn → một trợ lý (Điều phối nếu có trong nhóm); còn lại bộ chọn người nói (LLM, có cấu trúc) chọn 1–3 trợ lý phù hợp, không bắt cả ba cùng nói.
- Trợ lý nói lần lượt; người sau thấy câu của người trước nên hội thoại tự nhiên, không lặp ý.
- Trợ lý không phải thành viên không bao giờ được gọi; `@` trong đoạn trích dẫn (`"…"`, dòng `>`) hay trong địa chỉ email không phải là nhắc tên.

## Ví dụ mục tiêu (không phải kịch bản cố định)

> **Bạn:** Mọi người giúp mình lên kế hoạch cuối tuần nhé.
> **Nhật ký:** Nếu bạn muốn, mình có thể nhìn lại tuần vừa rồi qua những gì bạn đã ghi.
> **Hoạt động:** Mình có vài ý. Bạn muốn ưu tiên nghỉ ngơi hay thử điều mới?
> **Điều phối:** Vậy mình gộp hai hướng thành một kế hoạch vừa sức nhé…

## Không làm trong bản này

Nhóm nhiều người, trợ lý tự tạo, lời hỏi thăm định kỳ trong nhóm, thông báo đẩy.
