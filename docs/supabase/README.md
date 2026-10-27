# Supabase và PostgreSQL

Ứng dụng dùng Supabase cho PostgreSQL/pgvector và Auth. Browser làm việc qua BFF FastAPI; không có Supabase JS client truy cập trực tiếp bảng ứng dụng. Storage, Edge Functions, Realtime hoặc Supabase Cron không phải dependency của các luồng được mô tả hiện tại.

| Ranh giới | Triển khai |
| --- | --- |
| Application schema | `moodprint`, private, ngoài Data API |
| Provider schema | `auth`, do Supabase Auth sở hữu |
| Extension schema | `extensions`, có vector theo migration |
| Runtime access | SQLAlchemy/psycopg, role được cấp quyền tối thiểu |
| Migration access | Owner/operational route riêng, SQL đã review |
| End-user authorization | Backend ownership, purpose, pair và session checks |

Private schema và runtime grants là điều kiện cần, không thay thế checks ở backend. Repository không triển khai bộ end-user RLS cho schema `moodprint`; không mở schema qua Data API chỉ bằng cách cấp `anon/authenticated` SELECT. Một thiết kế direct-client mới cần threat model/policies/tests riêng.

Đọc [Auth và sessions](auth.md), [schema](schema.md), [migration workflow](migrations.md). Các mô tả ở đây dựa trên mã nguồn repository; không khẳng định revision/role/extension hosted đang ở trạng thái nào.

**Local PostgreSQL không tự có Supabase Auth.** Local fullstack tests tạo synthetic `auth.sessions` trong disposable DB để kiểm tra application behavior. Điều đó không phải Auth emulator dùng cho người dùng thật. Xem [development](../development.md).
