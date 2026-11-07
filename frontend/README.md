# MoodPrint frontend prototype

React + Vite + TypeScript, mobile-first, tiếng Việt. Chỉ sử dụng dữ liệu hư cấu và mock services trên trình duyệt. Không có backend, xác thực thật, AI/OCR, microphone/STT/TTS, email/SMS hay báo cáo thật.

## Chạy local

Yêu cầu Node.js 22.12+ (đã kiểm tra Node 24), npm.

```powershell
cd frontend
npm install
npm run dev
```

Mở URL Vite hiển thị (mặc định http://127.0.0.1:5173). Bỏ qua onboarding vẫn đi qua tài khoản demo. Chọn An, Minh, Hà hoặc Linh rồi **Vào thử với tài khoản demo**. Không nhập dữ liệu thật hay mật khẩu bạn đang dùng.

## Kiểm tra

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run check:boundaries
npm run format:check
npx playwright install chromium
npm run test:e2e
```

E2E tự mở Vite tại cổng 5178. Báo cáo HTML trong `playwright-report/`, trace lỗi trong `test-results/`. Build chỉ tạo file local `dist/`; không tự deploy. Không có `.env` hoặc API key cần thiết.

## Dữ liệu demo

- Zustand canonical store, versioned localStorage key `moodprint-demo`. Case, evidence, timeline, plan, chat, analysis, roleplay và support liên kết bằng ID; hồ sơ lọc theo ownerId.
- `/demo/school` là khu độc lập với key `moodprint-school-demo` và 48 reports riêng, không đọc student store.
- Settings → **Khôi phục dữ liệu mẫu** để xóa thay đổi student demo và đăng xuất. School Demo có nút reset riêng. Đăng xuất giữ bản ghi demo cục bộ để có thể tiếp tục persona cũ.
- Settings có lỗi lưu một lần để kiểm tra retry. Tìm kiếm vô nghĩa để xem empty state. Analysis có dữ liệu bị cắt, trùng và mâu thuẫn.
- UI dùng `mocks/services/demo.ts`; adapter chỉ tạo độ trễ và cập nhật state cục bộ. Không fetch hoặc telemetry.

## Walkthrough

Welcome → mock account → Home → AI → Chat → bộ 8 ảnh mẫu → mở phân tích → rà soát/sửa/xác nhận từng nguồn → xác nhận tạo hồ sơ → timeline → Kế hoạch ứng phó trong hồ sơ → chọn/điều chỉnh checklist → luyện nói 3 lượt → phản hồi → chuẩn bị lời nhắn → preview/bí danh → lưu báo cáo demo (chưa gửi).

Knowledge Hub ở Support, shortcut trên Home. Nguồn chính thức có nhãn phạm vi áp dụng và mở do người dùng chủ động. `/support/urgent` mở trực tiếp không yêu cầu tài khoản; nút 111 mở trình gọi của thiết bị, không tự gọi.

## Ranh giới kiến trúc

Code sản phẩm chỉ nằm trong frontend. `backend/README.md`, `agent/README.md` mô tả hướng phát triển sau này. `types/` là shared mock contracts; `features/` theo chức năng; `components/` là primitives/layout; `animations/` quản lý motion. Không khôi phục CI cũ. Xem `../docs/prototype/IMPLEMENTATION-EXECUTION.md` và báo cáo triển khai để biết coverage và bằng chứng.
