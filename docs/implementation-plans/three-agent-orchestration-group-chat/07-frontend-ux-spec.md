# 07 — UX/UI

Ngôn ngữ: tiếng Việt tự nhiên. Không hiển thị thuật ngữ nội bộ (handoff, agent, tool, run, SSE, worker, orchestration).

## Trang Trợ lý (`/assistants`)

- **Danh sách**: đúng ba trợ lý (avatar riêng: la bàn xanh rêu — Điều phối; sổ mở hổ phách — Nhật ký; ngôi sao nhảy san hô — Hoạt động), vai trò một dòng.
- **Nhóm AI** (cờ C): mục "Nhóm" với nút "Tạo nhóm"; mỗi nhóm hiện tên, chồng avatar thành viên, số tin chưa đọc.
- **Lịch sử**: nhóm theo trợ lý; hội thoại của trợ lý cũ có nhãn "Cuộc trò chuyện cũ".
- **Hội thoại cũ**: mở được, đọc/đổi tên/tải xuống/xóa; ô soạn tin thay bằng thông báo "Đây là cuộc trò chuyện cũ với Mây, chỉ để xem lại. Điều phối đã tiếp nhận phần việc này." + nút "Trò chuyện với Điều phối" (Cầu Nối → "Mở Tìm bạn").

## Chat với Điều phối (cờ B)

- Trạng thái thật từ server: "Điều phối đang hỏi Nhật ký một chút…" (chỉ khi có bước `consulting` thật).
- Sau câu trả lời: dòng nhỏ "Điều phối đã hỏi ý Nhật ký và Hoạt động" (chỉ từ receipt `completed` + `used_in_reply`).
- Khi Nhật ký trả lời trực tiếp: bong bóng mang avatar + tên Nhật ký; dải "Bạn đang trò chuyện với Nhật ký" + nút "Quay lại Điều phối".

## Nhóm

- **Tạo nhóm** (`/assistants/groups/new`): tên, ba thẻ chọn trợ lý (checkbox lớn, ≥ 2), giải thích ngắn "Các trợ lý chỉ thấy tin nhắn trong nhóm này; nhật ký riêng của bạn không được dùng nếu bạn chưa cho phép."
- **Chat nhóm** (`/assistants/groups/:id`): tiêu đề + chồng avatar; tin của từng trợ lý có avatar và tên ở đầu nhóm bong bóng; chỉ báo "Nhật ký đang trả lời…" theo event thật; trình chọn `@` (gõ `@` hoặc nút "Nhắc tên") — listbox có bàn phím (↑/↓/Enter/Esc), chèn token và ghi nhận ID ổn định; giữ bản nháp khi đổi trang.
- **Bảng thông tin nhóm**: thành viên (bỏ/thêm), công tắc nhật ký cho Nhật ký, đổi tên, xóa nhóm (xác nhận), giải thích quyền riêng tư.

## Chất lượng

Responsive 1440/768/390/360 không tràn ngang; focus trả về nút mở sau khi đóng hộp thoại; vùng chạm ≥ 44 px; tương phản AA; `prefers-reduced-motion` tắt mọi chuyển động; không có lỗi console.
