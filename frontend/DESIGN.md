# SafeVoice UI

Quy ước giao diện hiện có được triển khai trong [global.css](src/styles/global.css) và [refinement.css](src/styles/refinement.css). Phạm vi từng phần được mô tả ở [tính năng](../README.md#tính-năng-chính) và [kiến trúc](../README.md#kiến-trúc-hệ-thống). Student surfaces là Operate; Knowledge là Read; welcome là giới thiệu sản phẩm trong app.

Nền ngà xanh #F6FAF8, mặt trắng, chữ #183B37; primary #126A61; lavender cho luyện nói, peach cho kiến thức. Font system hỗ trợ tiếng Việt (spec cho phép fallback, không hotlink font). 16px body/1.6, display 28–40px; 4–64px spacing; border radius 12–16px. Logo hình nét thoại/dấu in tự thiết kế, icon Lucide. Orb làm dấu hiệu trạng thái mock, không đại diện chuyên gia.

Home: nhịp nhật ký cá nhân, hero xanh thoáng, 4 hành động, danh sách hồ sơ, thanh tiến độ, mục đọc nhẹ. Chat: transcript và composer, không grid dashboard. Analysis: nguồn được đánh số và phiếu xác nhận. Hồ sơ: workspace tài liệu, timeline; plan checklist. Knowledge: editorial lists và bài đọc. Admin: bảng/biểu đồ cùng dataset riêng.

Mobile 16px padding, bottom nav 4 mục/safe-area; desktop sidebar 224px, content max 1160px. GSAP scoped entrance 260ms, onboarding 350ms; CSS touch feedback. Tắt mọi motion theo preference hoặc settings. Modal dùng native dialog focus trapping, mobile bottom sheet.

Chat kết nối có bảng màu riêng trong [live.css](src/features/ai/live/live.css): nền charcoal `#1c201e`, bong bóng assistant `#2c312e`, bong bóng người dùng `#dce9df` với chữ tối. Header gọn giữ tên, trạng thái AI và lối vào hỗ trợ. Transcript cuộn độc lập, giữ vị trí khi đọc lại và có nút về tin mới nhất. Composer nằm dưới transcript, co giãn theo nội dung trong giới hạn viewport, với nút gửi/dừng và khoảng an toàn cho màn hình nhỏ, bàn phím. Approval dùng dialog sáng; citations và thao tác duyệt/sửa memory vẫn nằm trong luồng hội thoại. Ảnh giới thiệu lưu tại [.github/assets/readme](../.github/assets/readme/); ảnh và báo cáo QA ghi vào `frontend/test-results/`.
