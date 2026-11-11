# MoodPrint backend

Backend dùng FastAPI và import trực tiếp package Agent trong cùng tiến trình. Các hợp đồng dữ liệu dùng chung nằm trong `shared/`; schema PostgreSQL, role, quyền truy cập và RLS được quản lý bằng [migration Supabase](../supabase/migrations/).

Từ thư mục gốc repository, chuẩn bị môi trường local:

```powershell
uv sync --all-packages --all-extras --locked
uv run python scripts/dev/supabase_worktree.py start
uv run python scripts/dev/bootstrap_local_db.py
uv run python scripts/check.py
uv run python -m pytest -m integration
```

Bootstrap sinh mật khẩu cho role `moodprint_api` và tạo `.local/test.env` dành riêng cho test. Script chỉ chấp nhận Supabase local, không đọc hay ghi đè `.env` gốc. Chạy lại bootstrap sau mỗi lần reset database. Backend từ chối kết nối runtime bằng role `postgres`.

Gate ownership đọc policy từ baseline Git tin cậy; bản policy trong repo nằm tại [scripts/ownership.json](../scripts/ownership.json). Kiểm tra phạm vi migration dùng [schema manifest](../scripts/dev/schema-manifest.json). Xem [quy trình kiểm thử](../README.md#kiểm-thử). Muốn chạy UI/API với Supabase local và model scripted không cần provider, dùng `uv run python scripts/e2e_stack.py --project real --agent scripted` sau bootstrap.

Entry point API là `app.main:create_app`:

```powershell
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Cần cấu hình biến môi trường trước khi chạy. Retriever mặc định `pgvector` yêu cầu `VOYAGE_API_KEY` ngay khi khởi động; `.local/test.env` không cung cấp khóa này. Test offline chủ động truyền model và retriever giả lập. Chế độ fixture phải được chọn tường minh và không được dùng ở production. Các tính năng AI trực tiếp cần `OPENAI_API_KEY`.

`/health` kiểm tra tiến trình; `/ready` kiểm tra database và JWKS. Các route `/v1` xác thực JWT ES256 rồi chuyển giao dịch sang role `authenticated` với claim đã xác minh. Lifespan tự khởi động tác vụ reconcile lượt AI và dọn bằng chứng; các tác vụ này xử lý toàn database được cấu hình.

Đọc [kiến trúc](../README.md#kiến-trúc-hệ-thống) và [dữ liệu, bảo mật](../README.md#cách-hệ-thống-hoạt-động) để hiểu ranh giới runtime, Auth, RLS, Storage, phê duyệt và xóa tài khoản. [OpenAPI đã lưu](openapi.json) mô tả hợp đồng HTTP; mã route trong [app/api/v1](app/api/v1/) là nguồn đối chiếu khi thay đổi API.
