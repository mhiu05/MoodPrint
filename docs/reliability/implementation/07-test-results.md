# Kết quả test

Chạy trên worktree, không dùng database Supabase.

| Bộ | Kết quả |
|---|---|
| `pytest` hạn khách sau khi tách bước chuẩn bị, Postgres local `_test` | 1 passed trong 25 giây |
| `uv run ruff` trên file backend và script load đã sửa | passed |
| `uv run mypy` trên các module đã sửa | passed |
| Vitest `sessionPolicy`, `client`, `session` | 17 passed |
| `tsc --noEmit` | passed |
| Playwright `session-reliability.spec.ts` và `guest-expiry.spec.ts` trên cổng 5174 | 15 passed, sau đó thêm test ân hạn: 6/6 của file session passed |
| `scripts/check_docs.py` trước khi thêm thư mục implementation | passed |

Playwright lần đầu trỏ vào server Vite có sẵn ở cổng 5173 của workspace khác nên một test fail giả. Lần chạy đúng worktree, `PLAYWRIGHT_PORT=5174`, thì pass. CI không set biến này và vẫn dùng cổng 5173.

CI pull request của SHA `a28c73a` fail đúng một test: `test_ai_run_is_cancelled_at_the_deadline_without_waiting_for_the_monitor` nhận 401 `GUEST_EXPIRED` thay vì 202. Workflow push của cùng SHA thì pass. Fixture cũ chỉ còn 2 giây cho cả consent, tạo hội thoại và gửi tin. Hạn 7200 giây không đổi. Phần chuẩn bị giờ chạy khi còn 20 giây, rồi test chờ đến khi còn khoảng 2,2 giây mới gửi tin.

Chưa chạy toàn bộ pytest local trong phiên này. CI của commit mới sẽ chạy suite đó.

Load `SELECT 1` local: xem [08-performance-comparison.md](08-performance-comparison.md). Không có unexpected 5xx trong lần chạy thành công. Lần chạy trước đó fail 1.000/1.000 `InterfaceError` vì Windows ProactorEventLoop; script đã chuyển sang selector loop rồi chạy lại.
