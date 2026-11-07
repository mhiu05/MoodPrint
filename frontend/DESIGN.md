# MoodPrint UI

Kế thừa docs/prototype/04-DESIGN-SYSTEM.md. Student surfaces là Operate; Knowledge là Read; welcome là giới thiệu sản phẩm trong app.

Nền ngà xanh #F6FAF8, mặt trắng, chữ #183B37; primary #126A61; lavender cho luyện nói, peach cho kiến thức. Font system hỗ trợ tiếng Việt (spec cho phép fallback, không hotlink font). 16px body/1.6, display 28–40px; 4–64px spacing; border radius 12–16px. Logo hình nét thoại/dấu in tự thiết kế, icon Lucide. Orb làm dấu hiệu trạng thái mock, không đại diện chuyên gia.

Home: nhịp nhật ký cá nhân, hero xanh thoáng, 4 hành động, danh sách hồ sơ, thanh tiến độ, mục đọc nhẹ. Chat: transcript và composer, không grid dashboard. Analysis: nguồn được đánh số và phiếu xác nhận. Hồ sơ: workspace tài liệu, timeline; plan checklist. Knowledge: editorial lists và bài đọc. Admin: bảng/biểu đồ cùng dataset riêng.

Mobile 16px padding, bottom nav 4 mục/safe-area; desktop sidebar 224px, content max 1160px. GSAP scoped entrance 260ms, onboarding 350ms; CSS touch feedback. Tắt mọi motion theo preference hoặc settings. Modal dùng native dialog focus trapping, mobile bottom sheet.
