# MoodPrint
Dự án startup chương trình tiền ươm tạo, dự án giúp cho người dùng hiểu cảm xúc của bản thân hơn và kết nối tới mọi người xung quanh.

React/Vite/TypeScript frontend và Python 3.12.13/FastAPI backend dạng Modular Monolith. Pydantic là nguồn schema; TypeScript được tạo từ OpenAPI. Database chính thức: Supabase PostgreSQL/Auth. OpenAI Agents SDK Python dùng chung cho năm trợ lý.

Trạng thái từng task và giới hạn kiểm chứng: [implementation-status](docs/plans/implementation-status.md). Hướng dẫn vận hành: [deploy/README.md](deploy/README.md).

## Chạy local

Frontend:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Backend, trong terminal khác:

```powershell
cd backend
uv sync --locked
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
uv run python ../scripts/check_config.py
uv run python -m app
```

Frontend tại `http://127.0.0.1:5173`, API tại `http://127.0.0.1:8001`. Proxy Vite giữ request cùng origin. Điền cấu hình trong `backend/.env`; không commit hoặc gửi secret trong chat. Chưa đủ cấu hình thì UI báo unavailable, không dùng dữ liệu/AI giả thay thế. Đăng nhập mới có eligibility `unknown`; nhập năm sinh và xác nhận đã đủ16 tuổi để dùng tính năng cá nhân. Tìm bạn và nhắn tin người thật cần18 tuổi; ở năm tròn18 cần xác nhận đã đủ18, có thể làm sau trong cài đặt. Backend dẫn xuất quyền theo chính sách tự khai báo người dùng đã chốt24/10/2026, không tự bật consent.

Database local tùy chọn:

```powershell
docker compose -f deploy/compose.local.yml up -d
cd backend
$env:DATABASE_MIGRATION_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:55432/moodprint'
uv run alembic upgrade head
uv run alembic check
```

Mật khẩu trên chỉ dành cho container local bind127.0.0.1. Local PostgreSQL không thay thế Supabase Auth; synthetic auth/model chỉ nằm trong automated test harness. Không chạy remote migration từ các lệnh này.

## Kiểm tra

```powershell
cd backend
uv run --locked ruff check app tests
uv run --locked mypy app
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:55432/moodprint_test'
uv run --locked pytest -q
uv run --locked python ../scripts/export_openapi.py
cd ../frontend
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

PostgreSQL tests chỉ chấp nhận database disposable có hậu tố `_test`; thiếu TEST_DATABASE_URL thì skip rõ ràng. Không dùng SQLite cho locks/concurrency. Cài Chromium bằng `npx playwright install chromium` hoặc đặt `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` trỏ tới Chrome cài sẵn.

Full-stack thật với hai phiên tổng hợp, PostgreSQL và SDK fake model, không mock HTTP:

```powershell
# Từ repository root; tạo database một lần trong container local.
docker compose -f deploy/compose.local.yml exec database createdb -U postgres moodprint_e2e_test
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:55432/moodprint_e2e_test'
./scripts/test-fullstack.ps1
```

Harness dùng riêng các port8002/5174 và tự dừng process do nó tạo. Không gọi OpenAI thật, không ghi Supabase từ xa. Test model thật cần cấu hình và budget cho phép riêng; kết quả fake model không được báo như live M1/eval.

Harness Python dùng được trên Windows/Linux và trong CI, sau khi đã đặt `TEST_DATABASE_URL` như trên:

```powershell
cd backend
uv run --locked python ../scripts/test_fullstack.py
```

Kiểm tra cấu hình không in secrets: `uv run python ../scripts/check_config.py`. Kiểm tra Supabase chỉ đọc: `uv run python ../scripts/inspect_database.py`. Xem [configuration required](docs/plans/validation-artifacts/configuration-required.md) để xử lý lỗi kết nối đã quan sát; không chạy remote migration trước khi review target/schema/role/SQL và được phép.
