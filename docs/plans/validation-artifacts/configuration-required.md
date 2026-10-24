# CONFIGURATION REQUIRED

24/10/2026, Asia/Bangkok. Không chứa secrets.

**P01.01/P01.02 — Supabase `roznanxbiyqybjpvtilq`.** MCP và Connect đã xác minh đúng project. Chỉ cập nhật `DATABASE_URL`, `DATABASE_MIGRATION_URL`: sửa database path bị dính URL, percent-encode qua URL parser, thêm `sslmode=require`. `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` đã đúng nên giữ nguyên. OpenAI/model/session/security values giữ nguyên. Không sửa `.gitignore`, không commit `.env`.

**Kết quả:** [probe backend cuối](supabase-direct-inspection.json) — cả hai URL hiện dùng Session Pooler5432 IPv4, DNS/TCP/TLS1.3 PASS, certificate được kiểm tra ở network probe; password authentication FAILED. DirectIPv6 từng qua network/TLS nhưng [lượt sau timeout TCP](supabase-ipv6-transient-timeout.json), nên chuyển migration sang Session Pooler; compatibility DDL transaction đã rehearsal local, kết nối Alembic hosted vẫn chờ password. Hai URL dùng `sslmode=require` để bắt buộc mã hóa; chưa tuyên bố driver dùng `verify-full`. Endpoint/username đã đọc từ Connect, không suy từ region. Auth settings HTTP200/email enabled không thay thế login thành công.

**Thao tác người dùng còn thiếu:** nhập đúng PostgreSQL password ở terminal local. Chạy nguyên dòng sau từ bất kỳ thư mục nào; không dùng `Set-ExecutionPolicy` và không gửi password vào chat:

```powershell
uv run --directory E:\MoodPrint\backend python E:\MoodPrint\scripts\configure_database.py --host aws-0-ap-northeast-1.pooler.supabase.com --username postgres.roznanxbiyqybjpvtilq --migration-mode session
```

Script hỏi password ẩn hai lần, không nhận password qua command argument, không gọi mạng; chỉ sửa DB URLs và đặt pool mode session. Nếu không nhớ password, người dùng tự reset trong Dashboard sau khi kiểm tra các consumer khác, rồi chạy script. Không cần cung cấp lại OpenAI API key.

Password cần nhập là **Database Password đặt lúc tạo project `database`**, không phải mật khẩu tài khoản Supabase hoặc publishable/API key. Người dùng đã chạy script thành công tại local, cập nhật `DATABASE_URL`, `DATABASE_MIGRATION_URL`, `DATABASE_POOL_MODE`; probe sau đó vẫn bị Supabase từ chối password. Người dùng đã báo sẽ reset đúng project rồi cập nhật local; chưa báo hoàn tất lần reset này. Không coi thông báo sẽ thực hiện là kết nối đã thành công.

Sau đó kiểm tra chỉ đọc:

```powershell
uv run --directory E:\MoodPrint\backend python E:\MoodPrint\scripts\check_config.py
uv run --directory E:\MoodPrint\backend python E:\MoodPrint\scripts\inspect_database.py
```

`inspect_database` trả exit1 khi kết nối/inspection thất bại, phân biệt DNS/TCP/TLS/authentication/permission/revision; không in raw provider errors, SQL URLs hoặc credentials. Không dùng test reset scripts với hosted URLs.

**Remote migration readiness:** [catalog/Dashboard evidence](supabase-mcp-inspection.json) xác nhận PostgreSQL17.11, Auth27 bảng, chưa có application schema/history/roles. Thiết kế GRANT Auth cũ không thấy row do Auth RLS. [SQL Auth bridge và phạm vi](supabase-auth-rls-review.md), [SQL đầy đủ mới](supabase-initialization-auth-review.sql) và [rehearsal mới PASS](supabase-auth-rls-rehearsal.json) đã được chuẩn bị. Người dùng đã phê duyệt bản mới đúng hash/phạm vi. Runtime vẫn chưa có least-privilege LOGIN/password riêng; bản review tạo hai role NOLOGIN, không tự cấp credentials. Không dùng privileged runtime URL hiện tại như cấu hình release.

[Báo cáo PASS/FAIL/BLOCKED từng nhóm](supabase-validation-groups.md) và runner `scripts/apply_supabase_review.py --auth-rls` đã chuẩn bị. Default runner chỉ review offline; chưa chạy `--apply`. SQL mới được duyệt SHA256 `90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0`; không cần duyệt lại bản này. Bản cũ giữ nguyên nhưng không dùng để apply. Chỉ chạy artifact mới một lần sau kết nối đọc PASS; không gọi thêm Alembic online upgrade/stamp hoặc Supabase apply_migration cho cùng DDL.

**Chưa kiểm được:** backend persistence trên hosted DB, Supabase account login/onboarding thật, remote runtime privileges, live M1. Không tạo tài khoản Auth hoặc ghi domain data trong lần chẩn đoán.

**Đã tiếp tục độc lập:** ngoài explicit Nhịp mood-range tool, đã sửa cancellation trước coroutine entry, idempotent/shielded terminal cleanup, pending metadata retry và shutdown RAM clearing; backend135 tests PASS. UI hiện tại giữ nguyên, chưa có range selector. [Live smoke plan](live-ai-smoke-plan.md) chỉ là chuẩn bị, không bật provider.

AI/STT disabled, live API calls0. Provider privacy/retention và ngân sách usage cần duyệt riêng trước live AI/STT. Durable cost accounting, cancellation/recovery matrix, matching delivery, provider/backup deletion và evals vẫn còn task PARTIAL. Q04 self-declaration16/private18/social đã chốt; Q07 report staffing còn mở.
