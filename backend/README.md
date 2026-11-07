# MoodPrint backend

FastAPI import trực tiếp package Agent trong cùng deployment. Shared contracts nằm trong `shared/`; PostgreSQL schema, roles và RLS được quản lý duy nhất bằng Supabase CLI SQL migrations.

Local:

```powershell
uv sync --all-packages
uv run python scripts/dev/supabase_worktree.py start
uv run python scripts/dev/bootstrap_local_db.py
uv run python scripts/check.py
uv run pytest -m integration
```

Bootstrap tạo `.local/test.env` riêng cho test, không đọc hoặc ghi đè `.env` của owner. Khi chạy API local, nạp các biến của file này vào process rồi dùng `uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`. Không dùng role `postgres` làm runtime.

`/health` không gọi dependency. `/ready` kiểm DB và JWKS. Các route `/v1` xác thực JWT ES256; UoW dùng claims đã verify và `SET LOCAL ROLE authenticated` cho từng transaction. Schema ứng dụng không được expose qua Data API.

Companion Phase 0 chỉ có diagnostic tool. Offline tests dùng SDK `ScriptedModel`, không cần OpenAI key. Live call chỉ dùng model đã duyệt và cần cost ceiling riêng. Frontend Phase 0 giữ nguyên demo; Phase 1 chưa được triển khai khi G0 chưa đạt.

Xem `docs/implementation/reports/phase-0-report.md` tại repository root để biết bằng chứng và blocker thực tế. Chỉ dùng synthetic data; chưa sẵn sàng cho dữ liệu học sinh thật.
