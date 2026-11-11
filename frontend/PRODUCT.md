# SafeVoice
<!-- impeccable:product-schema 1 -->
## Platform
web
## Users
Học sinh 11–17 tuổi; School Admin Demo là khán giả riêng với dữ liệu tổng hợp giả.
## Product Purpose
Giúp hiểu tình huống, kể và làm rõ, ghi nhận, chuẩn bị bước tiếp theo, luyện nói và tìm người hỗ trợ.
## Capabilities and Constraints
React/Vite/TypeScript + FastAPI + Agents SDK + Supabase Auth/PostgreSQL/Storage. Hai workspace: tài khoản thật với quyền sở hữu dữ liệu và demo độc lập trong trình duyệt. 4 tab Home/AI/Hồ sơ/Support; Action Plan bên trong hồ sơ. Companion kết nối là opt-in, có approval/consent trước thao tác tương ứng; voice là demo. Không tự gửi tin cho trường/người khác. Phạm vi hiện có và giới hạn của UI/API xem [tính năng](../README.md#tính-năng-chính); các thành phần và luồng tích hợp xem [kiến trúc](../README.md#kiến-trúc-hệ-thống). School Admin chỉ là demo với dữ liệu hư cấu, tách khỏi hồ sơ học sinh. Chỉ thử nội dung hư cấu, không deploy.
## Brand Commitments
Calm, supportive, tuổi phù hợp, tiếng Việt, không phán xét; uncertainty minh bạch, không ẩn danh tuyệt đối.
## Evidence on Hand
Bộ dữ liệu dựng sẵn: [30 tình huống, 12 hội thoại và 6 kịch bản luyện nói](src/mocks/scenarios/index.ts), [8 ảnh chụp hư cấu](src/features/ai/analysis-model.ts), [24 bài kiến thức](src/mocks/data/knowledge.ts) và [48 báo cáo School Admin mẫu](src/features/school-admin/school-data.ts). Đây là số lượng fixture trong mã, không phải người dùng thực tế hay kết quả đánh giá mô hình.
## Accessibility & Inclusion
44px controls, visible focus, semantic landmarks, reduced-motion, mobile 320–1440px, urgent help public.
