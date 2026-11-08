# MoodPrint frontend

React, Vite và TypeScript. Phase 1 hỗ trợ hai workspace: tài khoản Supabase với dữ liệu nghiệp vụ qua FastAPI, và demo chạy độc lập trên trình duyệt. Chỉ sử dụng tài khoản thử nghiệm và nội dung hư cấu.

## Chạy local

Yêu cầu Node.js 22.12+ và npm. Từ `frontend/`:

```powershell
npm install
npm run dev
```

Vite đọc `.env` ở root và chỉ đưa biến có tiền tố `VITE_PUBLIC_` vào ứng dụng: `VITE_PUBLIC_SUPABASE_URL`, `VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `VITE_PUBLIC_API_BASE_URL`. Không đặt secret key hoặc database URL trong biến frontend. Không cần cấu hình backend để bấm **Vào thử với tài khoản demo**.

## Dữ liệu và xác thực

- `services/composition.ts` chọn adapter theo `workspace.kind`. Component gọi port; lỗi HTTP hiện lỗi và cho thử lại.
- Supabase JavaScript SDK chỉ dùng Auth, với PKCE, khôi phục phiên và tự làm mới token. Dữ liệu hồ sơ, evidence, kế hoạch, người tin cậy, bản nháp hỗ trợ và trạng thái đọc đi qua FastAPI.
- Store `useWorkspaceStore` là cache trong bộ nhớ khi đăng nhập thật. Alias `useDemoStore` giữ tương thích prototype. Chỉ workspace demo được persist trong `moodprint-demo`; dữ liệu demo không được chuyển lên server.
- Chat, phân tích mẫu, roleplay và voice còn mô phỏng. Trong tài khoản thật, state này nằm riêng tại `moodprint-sim-v1:<userId>`. Bộ ảnh mẫu không thể gắn vào hồ sơ thật. Knowledge catalog vẫn local đến Phase 2.
- Evidence thật dùng `tus-js-client`, signed upload capability từ backend, chunk 6 MB, pause/resume và cấp lại token khi cần. Không ghi đè bản gốc. Signed download URL chỉ dùng tạm thời, không ghi vào store.
- Hết phiên giữ bản nháp biểu mẫu theo user để đăng nhập lại. Đăng xuất chủ động dừng upload, xóa cache và bản nháp/simulation của user đó. Settings của tài khoản thật có thể xóa dữ liệu demo riêng trên trình duyệt.
- `/demo/school` dùng `moodprint-school-demo` độc lập. `/support/urgent` luôn công khai và không phụ thuộc backend; nút 111 mở trình gọi khi người dùng bấm.

## Kiểm tra

```powershell
npm run typecheck
npm run lint
npm test -- --maxWorkers=2
npm run build
npm run check:boundaries
npm run format:check
npm run test:e2e -- --project=demo
```

Project E2E `real` cần local Supabase và FastAPI; xem `../docs/implementation/07-TESTING-AND-ACCEPTANCE-CRITERIA.md`. Test chỉ dùng dữ liệu tổng hợp. Ảnh chụp prototype chỉ cập nhật khi chủ động bật `CAPTURE_SCREENSHOTS=1`.

Sinh lại TypeScript contract sau khi cập nhật `backend/openapi.json`:

```powershell
npx openapi-typescript ../backend/openapi.json -o src/services/http/schema.gen.ts
```

HTTP chỉ được phép trong `src/services/http/`. Boundary check chặn secret trong source/bundle, SDK ngoài phạm vi, socket, telemetry và microphone. Build tạo `dist/`, không tự deploy.
