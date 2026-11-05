# MoodPrint

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

MoodPrint giúp người dùng hiểu cảm xúc qua nhật ký và ba trợ lý Điều phối, Nhật ký, Hoạt động. Giao diện tập trung vào Trợ lý, Nhật ký và Tài khoản; giao diện tìm bạn, chat người với người và hoạt động đôi đã được gỡ. Backend social vẫn giữ để bảo toàn tương thích và dữ liệu.

## Operating Context

Code hiện tại dùng React 19, Vite và TypeScript. Chat AI có giao diện desktop và mobile web, lịch sử hoặc hội thoại tạm thời, nhập văn bản và nhập bằng giọng nói khi khả dụng.

## Capabilities and Constraints

- Dữ kiện từ code: server xác nhận lượt AI bằng accepted run, sau đó phát kết quả cuối; UI không nhận các giai đoạn suy luận chi tiết.
- Dữ kiện từ code: hủy là yêu cầu dừng, phải đợi kết quả cuối từ server. Chưa có tạm dừng rồi tiếp tục cùng một phản hồi.
- Dữ kiện từ code: metadata tin nhắn hiện có thao tác hover, focus bàn phím và chạm trên mobile; thiết kế mới phải giữ các hành vi này.
- Nhật ký saved có thể được lập chỉ mục qua Voyage khi đủ quyền; notice và công tắc opt-out nằm ở Tài khoản. Guest không được tự động lập chỉ mục.
- Người dùng yêu cầu không tự ý sửa .gitignore.

## Brand Commitments

- Tên sản phẩm MoodPrint, tên và avatar trợ lý lấy từ ứng dụng hiện có.
- Người dùng chọn ngày 30/10/2026: đổi toàn bộ diện mạo chat theo hướng Grok, giao diện gọn và UX tự nhiên hơn.
- Nguồn tham khảo do người dùng chỉ định: https://x.ai/bot, https://github.com/Jakubantalik/thinking-orbs, https://github.com/pbakaus/impeccable, https://github.com/greensock/gsap.

## Evidence on Hand

- README.md, frontend/src/features/real/RealApp.tsx, AIActivityStatus.tsx, aiActivityView.ts và frontend/src/styles/me2we.css.
- Ảnh màn chat Cầu Nối người dùng gửi trong cuộc hội thoại.
- Trang x.ai/bot đọc được nội dung bằng web fetch; trình duyệt tự động bị Cloudflare chặn. Không có bằng chứng đã kiểm tra demo tương tác trực tiếp.

## Product Principles

- Trạng thái hiển thị phải phản ánh vòng đời thực tế của request/run.
- Người dùng luôn có cách rõ ràng để gửi và yêu cầu dừng phản hồi.
- Nội dung cuộc trò chuyện là trọng tâm của màn chat.

## Open Decisions

Chưa xác nhận nghiên cứu persona, mục tiêu kinh doanh hoặc yêu cầu accessibility riêng ngoài phạm vi UI chat. Không suy diễn các điều này từ thiết kế tham khảo.
