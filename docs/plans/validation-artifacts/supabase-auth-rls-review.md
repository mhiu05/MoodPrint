# Auth RLS correction — SQL đã được phê duyệt, chờ kết nối

24/10/2026, Asia/Bangkok. Project `roznanxbiyqybjpvtilq`. Chưa thực thi DDL remote.

## Phát hiện từ catalog Supabase thật

`auth.sessions` thuộc `supabase_auth_admin`, bật RLS, không FORCE RLS và không có policies. Role `postgres` có SELECT/BYPASSRLS; runtime dự kiến không có BYPASSRLS. Vì vậy **GRANT SELECT(id,user_id) không đủ**: runtime nhận không row, làm backend từ chối cả session hợp lệ. Review trước chưa kiểm đủ đặc điểm RLS này; phép thử cũ chỉ SELECT LIMIT0 nên không phát hiện việc lọc row.

Người dùng đã phê duyệt bản cũ SHA256 `f94b6032a3685070effb01d1b496d7769cef5880e045738f346c09b3a0f77f7a`. Bản cũ được giữ nguyên và chưa thực thi. Phê duyệt đó không được tự chuyển sang bản sửa có privileged function.

Người dùng đã phê duyệt riêng **“Phê duyệt bản SQL mới đúng hash và phạm vi”** ngày 24/10/2026 cho bản mới SHA256 `90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0`. Bản mới thay thế bản cũ để thực thi; không cần xin duyệt lại nội dung này. Chưa gửi DDL vì probe backend cuối vẫn bị từ chối password; người dùng đang reset đúng project và cập nhật local.

## Phương án đề nghị

[SQL mới đầy đủ](supabase-initialization-auth-review.sql), SHA256:

```text
90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0
```

Giữ nguyên 24 bảng, 34 FK, 14 CHECK, 9 UNIQUE constraints, 5 unique partial indexes, RLS trên24 bảng, hai role NOLOGIN và toàn bộ Alembic0001–0005. Thay đổi phần security bootstrap:

- Bỏ GRANT USAGE trên schema Auth và SELECT cột Auth cho runtime.
- Tạo **một hàm private** `moodprint.is_provider_session_active(app_session_id uuid, app_user_id uuid) RETURNS boolean`. Không nhận trực tiếp Auth subject/provider session tùy ý. Hàm join app session→app user→provider session; kiểm đúng owner pair, local revoked/expiry/auth version/user status và sự tồn tại provider session.
- Hàm **SECURITY DEFINER**, owned by `postgres`, nên có thể đọc row Auth qua RLS bằng quyền owner. Đây là cầu nối quyền có chủ đích và là lý do cần duyệt nội dung mới. Runtime vẫn NOSUPERUSER/NOBYPASSRLS, không được đọc raw Auth rows hoặc tạo/sửa schema/function.
- `search_path=''`, mọi relation/function trong body được schema-qualify, parameters UUID, không dynamic SQL; chỉ trả boolean, không trả rows/token/password. Bind app-session/user ID do backend lấy sau xác minh opaque cookie. Authorization theo tuổi/consent/ownership vẫn ở FastAPI; không dùng user-editable JWT metadata.
- Thu hồi EXECUTE khỏi PUBLIC/anon/authenticated/service_role, chỉ cấp EXECUTE cho `moodprint_runtime`; schema moodprint vẫn không expose qua Data API. CREATE function và các REVOKE/GRANT nằm cùng transaction, không có cửa sổ public execution.

Không CREATE/ALTER/DROP/policy hoặc ghi dữ liệu vào bảng Auth hệ thống. Không thay RLS của Auth hoặc cấp BYPASSRLS cho runtime. [Supabase hướng dẫn](https://supabase.com/docs/guides/database/functions#security-definer-vs-invoker) giải thích quyền owner, search_path và giới hạn EXECUTE; [PostgreSQL](https://www.postgresql.org/docs/17/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY) yêu cầu bảo vệ search path/quyền gọi cho privileged functions. Kiểm owner trong hàm dùng app-session mapping vì ứng dụng xác thực bằng opaque backend cookie, không truyền JWT/auth.uid context vào SQL.

## Bằng chứng local

[supabase-auth-rls-rehearsal.json](supabase-auth-rls-rehearsal.json): **PASS** với Auth fixture bật RLS và không policies như remote.

- Tái hiện GRANT kiểu cũ nhưng vẫn không thấy provider row.
- Private helper thấy đúng session; sai user/local revoke/provider revoke trả false.
- Runtime không thể đọc trực tiếp hoặc sửa Auth, đọc cột ngoài scope, tạo bảng trong moodprint/public hoặc sửa Alembic revision.
- Catalog checks đúng24 bảng/RLS/constraints/roles/grants/function; schema/roles/fixtures rollback hoàn toàn.

Code FastAPI `verify_session` đã chuyển sang helper; health readiness yêu cầu helper tồn tại. Local Alembic online bootstrap và synthetic test fixtures dùng cùng SQL helper đóng gói trong `backend/app/infrastructure/database/provider_session.sql`, không sửa các revisions0001–0005. Offline export0001–0005 vẫn nguyên vẹn; helper là phần security bootstrap cùng ACL/RLS/roles.

## Thực thi bản đã được phê duyệt

Dùng **chỉ bản mới**, runner `apply_supabase_review.py --auth-rls --apply --approved-sha256 90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0` sau khi password probe PASS. Không chạy bản cũ trước, không chạy thêm Alembic online/stamp/Supabase apply_migration sau initialization. Runner so khớp exact hash, Alembic body và helper source, kiểm project/TLS/schema absence; runner từ chối bản legacy khi Auth bật RLS. Post-check fingerprint cấu trúc/RLS/policies Auth trước/sau phải giữ nguyên.

Runtime LOGIN/password vẫn là thao tác secret local sau migration. Hai test accounts đã được user cho phép, chưa tạo. Public Auth settings hiện signup enabled, email auto-confirm false: E2E register cần xác nhận email hoặc xác nhận test users qua Auth Dashboard/API được phép; không insert/update trực tiếp auth.users.
