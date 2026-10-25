# MoodPrint web (`moodprint-web`)

React 19 + Vite + TypeScript SPA cho MoodPrint. Ứng dụng production chỉ gọi API thật của backend FastAPI (`/api/v1`, cùng origin); không có dữ liệu mẫu, nhân vật hư cấu hay phản hồi soạn sẵn. Điểm vào duy nhất là `src/main.tsx` → `src/features/real/RealApp.tsx`.

## Chạy local

```powershell
npm.cmd ci
npm.cmd run dev        # http://127.0.0.1:5173, proxy /api → MOODPRINT_API_PROXY (mặc định http://127.0.0.1:8001)
```

Backend phải chạy riêng (xem README gốc). Không có chế độ demo: khi API không sẵn sàng, giao diện báo lỗi thật.

## Kiểm thử

```powershell
npm.cmd run typecheck
npm.cmd test                 # vitest: logic thuần + production guard
npm.cmd run build
npm.cmd run test:e2e         # Playwright với API được giả lập bằng page.route (chỉ trong tests/)
```

Full-stack thật (FastAPI + PostgreSQL disposable + Chromium) chạy bằng `scripts/test_fullstack.py` từ thư mục `backend/` — xem README gốc. Không sửa file trong `frontend/` khi bộ full-stack đang chạy (Vite HMR sẽ tải lại trang).

`src/productionGuard.test.ts` thất bại nếu mã production import lại `mocks/`, `state/`, `domain/`, `pages/` hoặc companion soạn sẵn, nếu `UI.tsx` export thành phần không dùng, hoặc nếu package không mang tên `moodprint-web`.

## Hợp đồng API

Kiểu TypeScript sinh từ OpenAPI của backend:

```powershell
cd ../backend; uv run --locked python ../scripts/export_openapi.py
cd ../frontend; npm.cmd run contracts:generate
```

## Cấu trúc

- `src/features/real/` — màn hình production (trợ lý AI, cảm xúc, ghi nhớ, quyền riêng tư, tìm bạn, tin nhắn).
- `src/api/` — client HTTP (CSRF, Idempotency-Key), SSE và kiểu sinh tự động.
- `src/components/UI.tsx` — primitive dùng chung (`Button`, `Dialog`, `StatePanel`, `Motion`, `Typing`, `Brand`).
- `src/companions/` — avatar và danh tính hiển thị của năm trợ lý.
- `src/styles/` — design tokens và CSS toàn cục.
