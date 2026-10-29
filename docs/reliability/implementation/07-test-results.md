# Kết quả test

Chạy trên worktree, không dùng database Supabase.

| Bộ | Kết quả |
|---|---|
| `uv run pytest tests/test_session_reliability.py tests/test_foundation.py` | 27 passed |
| `uv run ruff` trên file backend và script load đã sửa | passed |
| `uv run mypy` trên các module đã sửa | passed |
| Vitest `sessionPolicy`, `client`, `session` | 17 passed |
| `tsc --noEmit` | passed |
| Playwright `session-reliability.spec.ts` và `guest-expiry.spec.ts` trên cổng 5174 | 15 passed, sau đó thêm test ân hạn: 6/6 của file session passed |
| `scripts/check_docs.py` trước khi thêm thư mục implementation | passed |

Playwright lần đầu trỏ vào server Vite có sẵn ở cổng 5173 của workspace khác nên một test fail giả. Lần chạy đúng worktree, `PLAYWRIGHT_PORT=5174`, thì pass. CI không set biến này và vẫn dùng cổng 5173.

Chưa chạy toàn bộ pytest và toàn bộ Playwright trong phiên này. Các suite đó sẽ chạy trên GitHub Actions của pull request.

Load `SELECT 1` local: xem [08-performance-comparison.md](08-performance-comparison.md). Không có unexpected 5xx trong lần chạy thành công. Lần chạy trước đó fail 1.000/1.000 `InterfaceError` vì Windows ProactorEventLoop; script đã chuyển sang selector loop rồi chạy lại.
