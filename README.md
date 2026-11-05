# MoodPrint
Dự án startup chương trình tiền ươm tạo, dự án giúp cho người dùng hiểu cảm xúc của bản thân hơn và kết nối tới mọi người xung quanh.

React/Vite/TypeScript frontend và Python 3.12.13/FastAPI backend dạng Modular Monolith. Pydantic là nguồn schema; TypeScript được tạo từ OpenAPI. Database chính thức: Supabase PostgreSQL/Auth. OpenAI Agents SDK Python dùng chung cho năm trợ lý.

Tài liệu kỹ thuật: [kiến trúc tổng thể](ARCHITECTURE.md), [mục lục docs](docs/README.md), [agents](docs/agents/README.md), [frontend](docs/frontend/README.md), [backend](docs/backend/README.md), [Supabase](docs/supabase/README.md), [matching](docs/matching/README.md). Kết quả và giới hạn kiểm chứng: [verification](docs/verification.md). Hướng dẫn vận hành: [deploy/README.md](deploy/README.md).

## Chạy local

Hướng dẫn cấu hình MVP local, phân biệt consent/lịch sử/provider và kiểm chứng
bằng PostgreSQL riêng: [chạy local và kiểm thử](docs/development.md).

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

Frontend tại `http://127.0.0.1:5173`, API tại `http://127.0.0.1:8001`. Proxy Vite giữ request cùng origin. Điền cấu hình trong `backend/.env`; không commit hoặc gửi secret trong chat. Chưa đủ cấu hình thì UI báo unavailable, không dùng dữ liệu/AI giả thay thế. MoodPrint dành cho người từ đủ 18 tuổi, gồm đăng ký, dùng thử và mọi tính năng cá nhân/kết nối. Backend kiểm tra khai báo tuổi trong database trên từng giao dịch; năm tròn 18 cần xác nhận đã qua sinh nhật. Đây là tự khai báo, không phải xác minh giấy tờ. Tài khoản chưa đủ điều kiện vẫn giữ dữ liệu và có luồng bảo mật để xuất/xóa dữ liệu, đăng xuất và rút quyền MATCH. Xem [chính sách 18+ và rollout 0020](docs/release/moodprint-18plus-0020-rollout.md).

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

Từ repository root, tạo PostgreSQL/pgvector riêng cho lượt kiểm thử (cần Docker đang
chạy). Script không dùng lại database hay volume của ứng dụng:

```powershell
./backend/.venv/Scripts/python.exe scripts/disposable_postgres.py
```

Script in đường dẫn `environment_file` chứa cấu hình cục bộ. Nạp file này vào
environment của terminal; không chép URL chứa mật khẩu vào source/log:

```powershell
Get-Content -LiteralPath '<environment_file vừa được in>' | ForEach-Object {
  $testKey, $testValue = $_ -split '=', 2
  Set-Item -LiteralPath "Env:$testKey" -Value $testValue
}
$env:APP_ENV='test'
```

```powershell
cd backend
uv run --locked ruff check app tests
uv run --locked mypy app
uv run --locked pytest -q
uv run --locked python ../scripts/export_openapi.py
cd ../frontend
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

PostgreSQL tests cần `TEST_DATABASE_URL` riêng; thiếu biến này thì skip rõ ràng.
Trước reset, fixture kiểm tra loopback thật, tên DB/owner và marker thuộc
`MOODPRINT_TEST_RUN_ID`, cùng `APP_ENV=test`; hậu tố `_test` đơn thuần chưa đủ.
Không dùng SQLite cho locks/concurrency. Cài Chromium bằng `npx playwright install chromium`
hoặc đặt `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` trỏ tới Chrome cài sẵn.

Full-stack thật với hai phiên tổng hợp, PostgreSQL và SDK fake model, không mock HTTP:

```powershell
# Từ repository root, sau khi nạp environment_file của container disposable ở trên.
# Không chạy song song pytest/full-stack dùng cùng TEST_DATABASE_URL.
./scripts/test-fullstack.ps1
```

Harness dùng riêng các port8002/5174 và tự dừng process do nó tạo. Không gọi OpenAI thật, không ghi Supabase từ xa. Test model thật cần cấu hình và budget cho phép riêng; kết quả fake model không được báo như live M1/eval.

Harness Python dùng được trên Windows/Linux và trong CI, sau khi đã đặt `TEST_DATABASE_URL` như trên:

```powershell
cd backend
uv run --locked python ../scripts/test_fullstack.py
```

Khi kiểm thử xong, từ root chạy `./backend/.venv/Scripts/python.exe scripts/disposable_postgres.py --remove <run_id>`
với run ID do script provisioning in ra. Cleanup chỉ xóa container có đúng label
quyền sở hữu và tmpfs của lượt đó; không xóa database/volume đang dùng khác.

Kiểm tra cấu hình không in secrets, từ `backend/`: `uv run --locked python ../scripts/check_config.py`. Kiểm tra Supabase chỉ đọc: `uv run --locked python ../scripts/inspect_database.py`. Xem [cấu hình](docs/backend/configuration.md), [xử lý sự cố](docs/backend/operations.md) và [migration runbook](docs/supabase/migrations.md); không chạy remote migration trước khi review target/schema/role/SQL và được phép.
