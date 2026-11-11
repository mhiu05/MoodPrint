# MoodPrint frontend

React, Vite và TypeScript. Frontend hỗ trợ workspace kết nối Supabase Auth/FastAPI và demo độc lập trên trình duyệt. Xem [tổng quan](../README.md#tính-năng-chính), [tính năng hiện có](../README.md#tính-năng-chính) và [kiến trúc](../README.md#kiến-trúc-hệ-thống). Dùng nội dung hư cấu để trải nghiệm và kiểm thử.

## Chạy local

Yêu cầu Node.js 22.12+ và npm. Từ `frontend/`, dùng lockfile đã có. Trên PowerShell có thể gọi `npm.cmd` để tránh chính sách chặn script `.ps1`:

```powershell
npm.cmd ci
npm.cmd run dev -- --config e2e/vite.demo.config.ts --port 5173 --strictPort
```

Mở `http://127.0.0.1:5173`, chọn **Bỏ qua** rồi **Vào thử với tài khoản demo**. Config `e2e/vite.demo.config.ts` đặt `envDir: false`, nên lệnh trên không đọc `.env` ở root và không cần Supabase, backend hay AI. Đảm bảo terminal không tự cung cấp các biến `VITE_PUBLIC_` kết nối dịch vụ nếu muốn chạy hoàn toàn độc lập.

Với workspace kết nối, chạy `npm.cmd run dev`. Vite dùng config mặc định để đọc `.env` ở root và chỉ đưa biến có tiền tố `VITE_PUBLIC_` vào ứng dụng: `VITE_PUBLIC_SUPABASE_URL`, `VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `VITE_PUBLIC_API_BASE_URL`, cùng `VITE_PUBLIC_AI_COMPANION` khi bật AI kết nối. Không đặt secret key hoặc database URL trong biến frontend. Xem [hướng dẫn chạy](../README.md#cài-đặt-và-chạy-local) để chuẩn bị backend và dữ liệu.

## Dữ liệu và xác thực

- `services/composition.ts` chọn adapter theo `workspace.kind`. Component gọi port; lỗi HTTP hiện lỗi và cho thử lại.
- Supabase JavaScript SDK chỉ dùng Auth, với PKCE, khôi phục phiên và tự làm mới token. Dữ liệu hồ sơ, evidence, kế hoạch, người tin cậy, bản nháp hỗ trợ và trạng thái đọc đi qua FastAPI.
- Store `useWorkspaceStore` là cache trong bộ nhớ khi đăng nhập thật. Alias `useDemoStore` giữ tương thích prototype. Chỉ workspace demo được persist trong `moodprint-demo`; dữ liệu demo không được chuyển lên server.
- Companion kết nối (chat, phân tích ảnh có consent, roleplay nhiều lượt, memory và approval) gọi qua FastAPI/Agents SDK. Bật bằng `VITE_PUBLIC_AI_COMPANION=live` hoặc đặt `localStorage` key `moodprint:ai-companion` bằng `live` trước khi tải ứng dụng. Mặc định tắt; cần backend, schema, corpus và provider phù hợp. Demo vẫn mô phỏng khi bật công tắc này. Scripted test không kiểm chứng chất lượng mô hình thật.
- Khi Companion kết nối chưa bật, chat/phân tích/roleplay mô phỏng được ghi nhãn và nằm riêng tại `moodprint-sim-v1:<userId>`. Voice chỉ là demo; ảnh mẫu không thể gắn vào hồ sơ thật. Knowledge Hub có tìm kiếm qua API thật, bên cạnh bài đọc local; schema/corpus hosted thiếu được báo lỗi, không thay bằng kết quả mẫu.
- Evidence thật dùng `tus-js-client`, signed upload capability từ backend, chunk 6 MiB theo cấu hình backend, pause/resume và cấp lại token khi cần. Không ghi đè bản gốc. Signed download URL chỉ dùng tạm thời, không ghi vào store.
- Hết phiên giữ bản nháp biểu mẫu theo user để đăng nhập lại. Đăng xuất chủ động dừng upload, xóa cache và bản nháp/simulation của user đó. Settings của tài khoản thật có thể xóa dữ liệu demo riêng trên trình duyệt.
- Support UI lưu nháp/prepared, sao chép và tải `.txt`; lưu không gửi tới trường. Adapter có các phương thức chia sẻ qua API nhưng UI chưa nối đầy đủ hành trình gửi. Các mốc báo cáo demo là mô phỏng do người xem bấm thử.
- `/demo/school` dùng `moodprint-school-demo` độc lập, chỉ có dữ liệu hư cấu; không đọc/sửa hồ sơ học sinh hay gọi API trường. `/support/urgent` luôn công khai và không phụ thuộc backend; nút 111 mở trình gọi khi người dùng bấm.

## Kiểm tra

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test -- --maxWorkers=2
npm.cmd run build
npm.cmd run check:boundaries
npm.cmd run format:check
npm.cmd run test:e2e -- --project=demo
```

Project E2E `demo` tự chạy Vite bằng config cô lập. Project `real` cần local Supabase/FastAPI và bộ chạy stack tương ứng; xem [kiểm thử và phạm vi xác minh](../README.md#kiểm-thử). Test dùng dữ liệu tổng hợp. Config Playwright mặc định vẫn khởi động demo server, nên chỉ đổi `--project=real` chưa đủ để dựng stack kết nối.

Các script `hosted-product.mjs`, `live-mvp.mjs` và `audit-product.mjs` là bộ kiểm thử chuyên biệt có điều kiện môi trường riêng; không cần cho demo. Không dùng bootstrap/reset local với hosted. Ảnh giới thiệu được lưu trong [.github/assets/readme](../.github/assets/readme/), với script [capture-readme.mjs](scripts/capture-readme.mjs). Playwright E2E và các script `refinement-screenshots.mjs`, `audit-product.mjs` ghi ảnh/báo cáo QA vào `frontend/test-results/`; đây là artifact local được Git bỏ qua.

Sinh lại TypeScript contract sau khi cập nhật `backend/openapi.json`:

```powershell
npm.cmd run gen:api
```

HTTP chỉ được phép trong `src/services/http/`. Boundary check chặn secret trong source/bundle, SDK ngoài phạm vi, socket, telemetry và microphone. Build tạo `dist/`, không tự deploy.
