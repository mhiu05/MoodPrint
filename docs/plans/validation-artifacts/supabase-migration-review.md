# Supabase migration review — bản cũ được giữ để truy vết

Kiểm tra ngày 24/10/2026, Asia/Bangkok. Project `database`, ID `roznanxbiyqybjpvtilq`. Không tạo project mới.

Đây là snapshot lịch sử trước initialization. Bản Auth bridge mới sau đó đã được duyệt và commit; [execution hiện tại](supabase-migration-execution.json) và [runtime verification](supabase-runtime-verification.json) PASS. Các mô tả schema chưa có/password FAIL bên dưới chỉ ghi trạng thái lúc review cũ.

**Bản này không dùng để apply.** Catalog sau đó phát hiện `auth.sessions` bật RLS không policies; GRANT hai cột không cho runtime thấy row. Rehearsal cũ LIMIT0 chưa kiểm row visibility. [Auth RLS review mới](supabase-auth-rls-review.md) thay quyền đọc trực tiếp bằng private helper boolean; người dùng đã phê duyệt riêng bản mới SHA256 `90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0`. SQL cũ giữ nguyên, chưa chạy; không apply bản cũ rồi chạy tiếp bản mới.

## Bằng chứng chỉ đọc

- MCP `get_project_url` xác nhận đúng URL project; PostgreSQL **17.11**, database/role MCP là `postgres`. Role này có CREATEDB/CREATEROLE/BYPASSRLS, không phù hợp cho runtime.
- `list_migrations` trả danh sách trống. Catalog cũng không có schema `moodprint`, bảng `alembic_version` ở bất kỳ schema, hoặc role tên `moodprint%`. Đây là database chưa khởi tạo ứng dụng, chưa phải drift của revision đã triển khai.
- Supabase Auth đã có 27 bảng hệ thống. `auth.sessions.id` và `user_id` đều UUID NOT NULL, phù hợp truy vấn kiểm tra session hiện tại. Không đọc dữ liệu người dùng/password/token.
- Dashboard Data API Settings expose **public, graphql_public**; extra search path **public, extensions**; automatically expose new tables đang bật. Không thay các settings này. Giữ `moodprint` ngoài Data API và thu hồi các quyền API trên schema mới.
- Security và performance advisors trả `lints: []`; đây chỉ là ảnh chụp hiện tại, chưa chứng nhận schema ứng dụng chưa được tạo.
- Connect xác nhận Session Pooler host/username đúng cấu hình local; Direct host cũng khớp project. Báo cáo [connection cuối](supabase-direct-inspection.json) tách DNS/TCP/TLS/authentication. IPv4 session hỗ trợ TLS1.3/certificate verified nhưng password hiện có bị từ chối ở cả hai URL. IPv6 direct từng qua TLS rồi [timeoutTCP](supabase-ipv6-transient-timeout.json), nên đã dùng session mode cho cả hai URL; không dùng transaction mode.

## SQL đề nghị duyệt

[Bản SQL đầy đủ](supabase-initialization-review.sql), sinh từ [SQL Alembic nguyên bản](supabase-migrations-0001-0005.sql) bằng `scripts/prepare_supabase_migration.py`. Chỉ sinh offline; runner Alembic online vẫn từ chối hosted target.

Phạm vi:

1. Một transaction tạo schema `moodprint` owned by `postgres`; 23 bảng nghiệp vụ và `alembic_version`. 0001 tạo foundation, 0002 thêm safety, 0003 thêm lifecycle, 0004 thêm age declarations, 0005 mở rộng export scope VARCHAR32→64. Có 34 foreign keys, 14 CHECK, 9 UNIQUE constraints và 5 unique partial indexes ngoài primary keys; tất cả foreign keys chỉ trỏ trong `moodprint`.
2. Revision kết thúc `0005_export_scope`; không backfill tuổi hoặc consent, không nhập dữ liệu người dùng. Không CREATE/ALTER/DROP vào bảng/schema Auth, Storage hoặc Realtime. Không DROP/TRUNCATE/reset.
3. Tạo `moodprint_runtime` và `moodprint_app` **NOLOGIN**, không superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS. App là member của runtime; chưa có password hoặc đăng nhập khả dụng. Migration owner là `postgres`, tách khỏi app.
4. Runtime có USAGE schema, SELECT/INSERT/UPDATE/DELETE trên 23 bảng nghiệp vụ; chỉ SELECT revision. Không CREATE, TRUNCATE, ownership, quyền quản trị hoặc default grants cho bảng tương lai.
5. Chỉ thêm USAGE trên `auth` và SELECT **hai cột `id, user_id` của `auth.sessions`** cho runtime. Đây là thay đổi ACL cần duyệt; không cấp quyền sửa dữ liệu Auth hay đọc các cột khác.
6. Bật RLS cho cả 24 bảng. Policy cho role backend tin cậy dùng `USING(true) WITH CHECK(true)` trên bảng nghiệp vụ; bảng revision chỉ SELECT. Đây là hàng rào chống truy cập bằng Data API roles, **chưa phải tenant isolation tại PostgreSQL**: owner/consent/age/authorization vẫn do FastAPI kiểm tra. Không thêm policy `auth.uid()` khi backend không truyền JWT context vào SQL.

Preflight SQL dừng nếu database/owner không đúng hoặc schema/roles đã tồn tại; không ghi đè trạng thái khác. `lock_timeout=5s`, `statement_timeout=60s`; tạo bảng/index trong transaction trên schema mới, không cần concurrent indexes. Revision, ACL và RLS commit cùng nhau; lỗi rollback toàn bộ. Sau triển khai dùng forward migration, không destructive downgrade.

## Rehearsal thực tế

[Kết quả local](supabase-migration-rehearsal.json): **PASS** trên PostgreSQL17.11 local, database riêng `moodprint_schema_review_test`. Script chỉ chấp nhận local `*_test`, từ chối schema có sẵn, không reset dữ liệu. Bản local thay duy nhất database preflight và thêm Auth/API-role fixtures tổng hợp trong transaction.

Đã kiểm tra revision0005, RLS24 bảng, runtime CRUD thành công, DDL trong `moodprint`/`public` bị từ chối, không sửa revision, không sửa Auth hoặc đọc cột Auth ngoài phạm vi. Schema/roles/fixtures rollback; database local rỗng còn lại để chạy lại. Rehearsal không thay thế kiểm tra permissions trên Supabase.

## Điều kiện thực thi và phần còn thiếu

- Người dùng cập nhật PostgreSQL password **tại local**, không gửi chat. Kiểm tra kết nối từ backend thành công trước DDL; hiện dùng Session Pooler5432 cho runtime và migration vì IPv6 direct không ổn định. Sau khi authentication PASS, kiểm tra engine NullPool/transaction và schema grants qua session endpoint; Alembic remote guard vẫn giữ nguyên. Chỉ cân nhắc Direct lại khi có bằng chứng IPv6 ổn định.
- Người dùng đã duyệt **đúng file SQL và sáu phạm vi trên** ngày24/10/2026, SHA256 `f94b6032a3685070effb01d1b496d7769cef5880e045738f346c09b3a0f77f7a`. Đây là phê duyệt lịch sử; bản Auth bridge mới đã được duyệt riêng và thay thế cho thực thi. Chưa apply vì kết nối password từ backend vẫn FAIL, kể cả sau lần nhập local mới; người dùng đang tự reset/cập nhật password.
- Sau DDL cần provision password và bật LOGIN cho `moodprint_app` qua thao tác secret local được duyệt riêng; không dùng password `postgres` cho app. Kiểm tra custom-role pooler username từ Connect, thay riêng runtime URL; migration tiếp tục owner riêng. Việc này không nằm trong bản SQL NOLOGIN.
- Kiểm tra lại catalog/RLS/advisors, thực nghiệm runtime DML/noDDL, health, synthetic Supabase Auth + onboarding16/18 và persistence. Chưa tạo tài khoản Auth hoặc domain data trên hosted project.

Nguồn: [Supabase Connect](https://supabase.com/docs/guides/database/connecting-to-postgres), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Data API security](https://supabase.com/docs/guides/api/securing-your-api), catalog/MCP và Dashboard đúng project. Schema/role status là quan sát session này, không suy từ region hoặc tài liệu.
