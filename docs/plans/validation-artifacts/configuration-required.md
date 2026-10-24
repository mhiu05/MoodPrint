# CONFIGURATION REQUIRED

24/10/2026, Asia/Bangkok. Không chứa secrets.

**Supabase PostgreSQL: PASS.** Project `roznanxbiyqybjpvtilq`, PostgreSQL17.11. Hai Session Pooler5432 URLs dùng SSL; network probe xác minh certificate/TLS1.3. Driver hiện `sslmode=require`, không tuyên bố `verify-full`. Runtime là `moodprint_backend`, migration owner là `postgres`. [Probe](supabase-direct-inspection.json), [runtime verification](supabase-runtime-verification.json), [DML/outbox rollback/readiness200](supabase-runtime-transaction.json).

User đã nhập đúng DB password qua helper local. Thông báo cũ gộp ValueError/EOF/cancel nên không truy ngược được chính xác lỗi nhập cũ. Helper mới phân biệt empty/mismatch/invalid characters/project/host/file errors, kiểm round-trip dotenv/URI và chặn echo fallback. Reserved symbols/quotes/backslashes/Unicode PASS. Credential cũ bị từ chối ở cả pooler và direct; local update đã khắc phục. Không cần nhập/reset PostgreSQL password nữa.

**Migration: PASS, không replay.** SQL Auth bridge SHA256 `90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0` đã duyệt và commit một lần. Revision0005,24tables/RLS/constraints/helper/Auth fingerprint PASS. Không chạy legacy SQL, Alembic online/stamp hoặc MCP apply_migration lặp lại. [Execution](supabase-migration-execution.json).

Runtime template SHA256 `d9124bfd7747a7a04841b8e471a38ddfe6de04d87f91b20ffd63e3f79a1f0461` đã duyệt và commit. Runtime password sinh ngẫu nhiên local; SQL nhận SCRAM verifier. Hai group roles giữ NOLOGIN; backend LOGIN không admin/BYPASSRLS/CREATE/raw Auth. Probe đầu báo42501 do inspector dùng tên Auth relation; sửa catalog OID, không mở rộng grants. Chỉ dùng `provision_supabase_runtime.py --verify-only` khi cần kiểm tra lại.

**Test accounts:** user tự tạo2accounts qua Dashboard/Auto confirm; không dùng Admin key. Helper `--configure-existing` đã xác minh login/getUser và revoke riêng validation sessions. Credentials lưu local dưới `MOODPRINT_TEST_A_EMAIL`, `MOODPRINT_TEST_A_USER_ID`, `MOODPRINT_TEST_A_PASSWORD_B64` và nhóm B tương ứng. Base64 bảo toàn parsing, không phải mã hóa bảo mật. Không lấy password từ chat để đưa vào tool. `.env` không được Git theo dõi; không sửa `.gitignore`. OpenAI/model/session/security values giữ nguyên.

**Hosted E2E: PASS theo phạm vi thực thi.** Auth/DB/runtime thật, SDK fake model; login/onboarding/consent/owner isolation/memory/matching/concurrency/chat/restart/reveal/report/block/provider revoke/logout replay PASS. Nhịp UI chọn range→scoped tool/no notes/one-turn consent/a11y390/1440 PASS. Không reset schema/Auth. Public signup/SMTP/email-delivery/recovery chưa được chứng minh. Core drill giữ block của hai fixtures, nên không tự reset dữ liệu để rerun matching; cần cohort mới được cho phép hoặc workflow unblock đã review.

**Security advisor:** latest WARN leaked-password protection disabled. Tính năng này cần Pro+; hiện Free. Không mua dịch vụ hoặc tự đổi settings. Các schema/grants checks PASS;2FK performance INFO chờ review riêng.
**Live AI/STT: BLOCKED** bởi account privacy/retention và ngân sách explicit chưa chốt. Key/model đã có, không yêu cầu cung cấp lại. Durable accounting/fencing/recovery, processor/backup deletion và report staffing còn gate riêng. Xem [release readiness](release-readiness.md) và [task ledger](../implementation-status.md).
