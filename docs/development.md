# Chạy local và kiểm thử lặp lại

## 1. Công cụ và môi trường

Repository dùng Python **3.12.x** (CI chọn 3.12.13), `uv`, Node.js **22** trong CI, npm và Docker cho disposable PostgreSQL/pgvector. Dependencies đã khóa trong `backend/uv.lock`, `frontend/package-lock.json`; không cần thêm framework/test runner để đọc tài liệu.

```powershell
# repository root
uv --version
node --version
npm.cmd --version
docker version
git status --short
Push-Location backend
uv sync --locked
Pop-Location
Push-Location frontend
npm.cmd ci
Pop-Location
```

Không ghi đè `.env` hiện có. Sao chép example chỉ khi chưa có file, sau đó điền cấu hình bằng kênh riêng:

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) {
    Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
}
```

[Configuration](backend/configuration.md) liệt kê defaults, flags và dependency gates. `backend/local-mvp.env.example` chỉ là ví dụ local; Auth thật vẫn cần Supabase Auth cùng hệ thống database/session.

## 2. App bình thường

Terminal backend, từ `backend/`:

```powershell
uv run --locked python ../scripts/check_config.py
uv run --locked python -m app
```

Terminal frontend, từ `frontend/`:

```powershell
npm.cmd run dev
```

SPA: `http://127.0.0.1:5173`; API: `http://127.0.0.1:8001`. Vite proxy `/api` đến backend, có thể đổi bằng `MOODPRINT_API_PROXY`. Không đổi browser origin sang `localhost` tùy tiện khi backend origin/cookie đã cấu hình `127.0.0.1`.

Production UI không có fake data/model fallback. Thiếu DB/Auth/provider thì hiển thị unavailable thật. Login mới cần khai báo eligibility; AI/MEM/MATCH/VOICE cần quyền người dùng, không chỉ `.env` flag.

## 3. Database local

Compose mặc định tạo PostgreSQL có pgvector, bind loopback cổng 55432:

```powershell
docker compose -f deploy/compose.local.yml up -d --wait
docker compose -f deploy/compose.local.yml exec database createdb -U postgres moodprint_test
docker compose -f deploy/compose.local.yml exec database createdb -U postgres moodprint_e2e_test
```

Nếu database đã tồn tại, kiểm tra đúng target trước khi dùng lại; không reset dữ liệu ứng dụng thật. Mật khẩu `moodprint-local-only` chỉ dành cho container local công khai trong Compose.

Nếu Windows chặn port 55432, có thể dùng container disposable riêng như lần kiểm chứng tài liệu này:

```powershell
docker run --detach --rm --name moodprint-docs-db-20261028 --publish 127.0.0.1:15432:5432 --env POSTGRES_DB=moodprint_docs_test --env POSTGRES_USER=postgres --env POSTGRES_PASSWORD=moodprint-local-only pgvector/pgvector:0.8.2-pg17
```

Chọn tên/port trống của phiên mình; không dừng process/container người khác. Khi test xong, `docker stop moodprint-docs-db-20261028` dừng và xóa container `--rm` vừa tạo; dữ liệu test không được giữ. Compose mặc định có named volume riêng và không bị lệnh này tác động.

## 4. Backend static và PostgreSQL tests

Từ `backend/`, với container disposable ở 15432:

```powershell
uv run --locked ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/provision_supabase_runtime.py ../scripts/check_reviewed_artifacts.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py
uv run --locked mypy app
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:15432/moodprint_docs_test'
uv run --locked pytest -q
```

Nếu dùng Compose thay port thành 55432 và database tương ứng. Fixtures chỉ cho local psycopg URL, tên DB kết thúc `_test`, rồi drop/create application tables trong DB đó. Không dùng database local có dữ liệu cần giữ. Thiếu URL thì integration skip; không báo toàn bộ tích hợp đã đạt khi skip.

Migration verification dùng **DB khác**, chạy upgrade/current/check như [runbook](supabase/migrations.md). Pytest tạo ORM metadata không thay thế kiểm tra chuỗi Alembic từ DB rỗng.

## 5. Contracts và frontend

```powershell
# backend/
uv run --locked python ../scripts/export_openapi.py
# frontend/ trong terminal hoặc sau đổi directory
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Từ root kiểm tra drift:

```powershell
git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts
```

Browser fixture suite riêng server 5190:

```powershell
# frontend/
npx.cmd playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP\moodprint-browser-results"
```

Chromium cần có sẵn. Config mặc định `npm run test:e2e` dùng 5173 và có thể reuse dev server. [Testing frontend](frontend/testing.md) giải thích phạm vi mocks/fullstack/live và cách tránh commit artifacts.

## 6. Fullstack với synthetic actors

```powershell
# root, với container test ở 15432
docker exec moodprint-docs-db-20261028 createdb -U postgres moodprint_fullstack_test
Push-Location backend
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:15432/moodprint_fullstack_test'
uv run --locked python ../scripts/test_fullstack.py --reporter=list --output "$env:TEMP\moodprint-fullstack-results"
Pop-Location
```

Harness sở hữu ports 8002/5174, synthetic auth, real HTTP/database và SDK fake model. Không chạy cùng DB với pytest hoặc harness khác; không sửa frontend khi suite chạy. Runner dừng process nó tạo khi kết thúc, không dừng dev server khác. Kết quả không chứng minh live OpenAI/Voyage hoặc hosted Supabase.

## 7. Checks bổ sung

```powershell
# root, offline
uv run --project backend --locked python scripts/check_docs.py
uv run --project backend --locked python scripts/check_reviewed_artifacts.py
git diff --check
```

Deployment poller tests cần Linux (`fcntl`). Có thể chạy offline bằng image Python local và mount read-only; lệnh của lần kiểm chứng nằm trong [verification](verification.md). Không mock `fcntl` để báo Windows đã kiểm tra đúng runtime Linux.

CI còn kiểm tra dependency audit, load, actionlint và Docker/proxy packaging trong [verify.yml](../.github/workflows/verify.yml). Báo riêng checks đã chạy local và checks còn chờ CI; không coi việc push là CI đã đạt.
