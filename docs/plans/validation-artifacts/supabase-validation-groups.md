# Supabase verification groups — 24/10/2026

Project đích: `roznanxbiyqybjpvtilq`, Asia/Bangkok. Các kết quả dưới đây phân biệt kiểm tra remote chỉ đọc, rehearsal local và hosted E2E chưa chạy. Người dùng đã duyệt bản SQL Auth bridge mới; chưa gửi DDL.

| Nhóm | Kết quả | Bằng chứng và phạm vi |
|---|---|---|
| Project identity qua MCP | PASS | `get_project_url` đúng URL; catalog PostgreSQL17.11/database postgres; MCP role postgres |
| Định dạng hai PostgreSQL URLs | PASS | `check_config.py`; không hiển thị credentials |
| DNS/TCP/TLS từ backend | PASS | [probe](supabase-direct-inspection.json): cả hai Session Pooler5432, IPv4, TLS1.3/certificate verified ở network probe |
| Authentication bằng password local hiện có | FAIL | Người dùng đã chạy nhập password ẩn thành công ở local, nhưng probe sau đó vẫn bị từ chối ở cả hai URL; đã loại trừ env override, outer whitespace, publishable key; postgres LOGIN được và không hết hạn |
| Remote schema/history/roles | PASS — đã kiểm tra | Catalog chưa có moodprint, application roles hoặc Alembic table; `list_migrations=[]`; không có drift của ứng dụng đã triển khai |
| Alembic0001–0005 ↔ SQL review | PASS | Runner review-only sinh lại SQL offline và so khớp nguyên body đúng một lần; không chạy online upgrade hoặc stamp |
| Tables/constraints — local | PASS | [rehearsal Auth RLS mới](supabase-auth-rls-rehearsal.json): 24 bảng, 34 FK, 14 CHECK, 9 UNIQUE constraints, 5 unique partial indexes, revision0005 |
| RLS/role scope — local | PASS | RLS24; hai role NOLOGIN, không quyền quản trị/BYPASSRLS; app DML được, CREATE trong moodprint/public bị chặn |
| Auth column-grant design cũ | FAIL | Remote Auth sessions bật RLS/không policies; local tái hiện runtime không thấy provider row. Rehearsal cũ LIMIT0 chưa kiểm row visibility |
| Private Auth bridge mới — local | PASS | Helper boolean SECURITY DEFINER/search_path rỗng; valid session true, sai owner/local revoke/provider revoke false. Runtime raw Auth read/write denied; không sửa Auth structure/RLS/data |
| Transaction safety — local | PASS | Schema/roles/fixtures rollback; initializer từ chối schema đã tồn tại; artifact dùng một BEGIN/COMMIT cho DDL/revision/ACL/RLS |
| Remote migration/constraints/RLS/privileges | BLOCKED | SQL đã được user duyệt đúng hash; chỉ chờ password đúng. Người dùng đang tự reset đúng project rồi cập nhật local; chưa gửi DDL |
| Runtime LOGIN/health readiness | BLOCKED | Bản SQL chỉ tạo role NOLOGIN; cần provision credential runtime riêng qua terminal local sau migration |
| Hosted Auth + hai-account full-stack E2E | BLOCKED | Chưa khởi tạo DB/runtime. Người dùng đã cho phép hai test accounts; chưa tạo account hoặc ghi dữ liệu hosted |
| Live AI/STT | BLOCKED | Key/model đã có; account privacy settings và thử nghiệm có budget chưa được duyệt; API usage0 |

## Bản SQL có hiệu lực đã được người dùng phê duyệt

[supabase-initialization-auth-review.sql](supabase-initialization-auth-review.sql), SHA256:

```text
90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0
```

Phạm vi ở [Auth RLS review](supabase-auth-rls-review.md): 24 bảng trong moodprint, revision0005, RLS, hai role NOLOGIN, domain grants và một private helper boolean. Runtime chỉ EXECUTE helper, không có raw Auth privileges hoặc BYPASSRLS. Không bao gồm bật LOGIN/password runtime hoặc live AI. Không sửa bảng/RLS/dữ liệu Auth.

Người dùng đã trả lời **“Phê duyệt bản SQL mới đúng hash và phạm vi”** ngày24/10/2026. Không xin duyệt lại nội dung này khi password được sửa. Điều kiện trước apply là kết nối đọc từ backend phải PASS. Hai test accounts đã được cho phép tạo trong yêu cầu E2E, nhưng chưa tạo vì database/runtime chưa sẵn sàng; Auth hiện yêu cầu xác nhận email.

[Bản cũ](supabase-initialization-review.sql) đã được duyệt ở SHA256 `f94b6032a3685070effb01d1b496d7769cef5880e045738f346c09b3a0f77f7a` và giữ nguyên để truy vết. Bản mới thay thế bản cũ cho lần apply; không chạy nối tiếp cả hai.

## Cơ chế thực thi duy nhất đã chuẩn bị

`scripts/apply_supabase_review.py --auth-rls` mặc định **review-only**, không network/DDL. Bản mới đã được duyệt; sau password probe PASS chạy với `--apply --approved-sha256 90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0`.

Runner kiểm tra hash, so SQL với Alembic export/helper source, whitelist project/host/owner/port5432/TLS rồi preflight chỉ đọc. Runner từ chối thiết kế legacy khi Auth bật RLS. Nếu schema đã có thì dừng, không replay DDL. Chạy nguyên artifact mới một lần, ghi Alembic revision0001→0005 trong cùng transaction với schema/ACL/RLS/helper. Không chạy thêm `alembic upgrade`, `stamp` hoặc Supabase `apply_migration` cho initialization này.

Sau khi submit mà mất kết nối, ghi outcome unknown và yêu cầu inspection chỉ đọc; không tự retry DDL. Sau commit kiểm revision/table/constraints/RLS/roles/grants và fingerprint cấu trúc Auth trước/sau. Fingerprint chỉ đọc catalog, không đọc dữ liệu Auth. PASS của runner chỉ là migration verification; runtime LOGIN và app readiness/E2E vẫn là gates riêng.
