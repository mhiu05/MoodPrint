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

Companion hiện có persistent sessions, context/memory, nguồn tri thức, đề xuất mốc sự việc/kế hoạch có approval, phân tích ảnh có consent và roleplay nhiều lượt. Offline tests dùng SDK `ScriptedModel`, không cần OpenAI key. Live call chỉ dùng model đã duyệt, qua ngân sách/ledger hiện có; authorization cũ đã hết 900/900 calls. Không tạo client trả phí cho audit không được phép.

Audit Supabase hosted chỉ định dùng `scripts/hosted_product.py`, tách khỏi test local: [hướng dẫn](../docs/quality/product-completion/hosted.md). Nó tắt worker toàn cục và khóa user/path theo manifest. Không dùng trực tiếp lifespan production để audit bản ghi synthetic trong DB dùng chung. Xem [báo cáo sản phẩm](../docs/implementation/reports/product-completion-review.md) cho bằng chứng và schema blocker; không tự áp dụng migration hosted. Chỉ dùng synthetic data; chưa sẵn sàng cho dữ liệu học sinh thật.
