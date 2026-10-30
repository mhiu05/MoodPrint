# Backend

## Phân loại lỗi

`database_failure_category` chỉ trả `connection_limit`, `connection_unavailable`, `pool_timeout` hoặc `None`.

- SQLSTATE `53300`, hoặc lỗi kết nối không có SQLSTATE nhưng chứa cụm `too many connections`, thành `DATABASE_BUSY`, HTTP 503, `Retry-After: 2`.
- SQLSTATE họ `08xxx` / `57P01`–`57P03`, hoặc cụm mất kết nối khi không có SQLSTATE, thành `DATABASE_UNAVAILABLE`, HTTP 503, `Retry-After: 5`.
- `sqlalchemy.exc.TimeoutError` của pool thành `DATABASE_BUSY`.
- `ProgrammingError`, deadlock `40P01` và `RuntimeError` vẫn HTTP 500, `retryable: false`.

Response và log không chứa message của driver. Test nhét canary URL, mật khẩu và chữ riêng tư vào exception.

401 `SESSION_EXPIRED` không bị đổi thành 503.

Không thêm retry transaction ở backend.

## Log

Một dòng `request_completed` cho request dưới `/api/`: request id, route template, status, thời gian, category, loại exception, SQLSTATE, `RELEASE_SHA`, số kết nối đang checkout và overflow.

`RELEASE_SHA` đi từ file env của Compose vào container API. Giá trị lạ thành `unknown`.

Sweep định kỳ thêm `db_pool_checked_out` và `db_pool_overflow` khi pool thật có số đo. Database giả trong test không làm readiness bị lỗi.
