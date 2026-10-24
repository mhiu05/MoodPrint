# Supabase verification groups — 24/10/2026

Project `roznanxbiyqybjpvtilq`; Asia/Bangkok. Bằng chứng remote và local được phân biệt dưới đây.

| Nhóm | Kết quả | Bằng chứng/phạm vi |
|---|---|---|
| Identity/Connect | PASS | MCP ACTIVE_HEALTHY/ap-northeast-1/PostgreSQL17.11; Dashboard exact Session Pooler5432 |
| DNS/TCP/TLS/authentication | PASS | [Hai URLs](supabase-direct-inspection.json), runtime/migration identities riêng, network certificate/TLS1.3 |
| Input/URI helper | PASS | Safe error codes, hidden-input echo fail-closed, reserved symbols/Unicode/backslash round-trip |
| Alembic/hash/execution | PASS remote | [Commit](supabase-migration-execution.json) một lần, exact approved full SHA256, không trùng DDL |
| Tables/revision/constraints | PASS remote |0005;24tables/24PK/34FK/14CHECK/9UNIQUE/5partial unique indexes |
| RLS/API exposure | PASS remote | RLS24; anon/authenticated không USAGE moodprint; giữ Data API public/graphql_public |
| Auth helper/boundary | PASS remote + local | Runtime chỉ EXECUTE boolean; no raw Auth. Auth27 tables và structure/RLS/policies fingerprint không đổi; local owner/revoke cases PASS |
| Legacy Auth column grant | FAIL — superseded | Auth RLS/no policies lọc row; rehearsal LIMIT0 cũ chưa phát hiện. Không chạy legacy SQL |
| Role separation | PASS remote |2group NOLOGIN + backend LOGIN; no admin/BYPASSRLS/CREATE/raw Auth. [Verification](supabase-runtime-verification.json) |
| Runtime transaction/readiness | PASS remote | [DML/outbox rollback](supabase-runtime-transaction.json), parameterized synthetic rows không commit; ready200 |
| Security advisors | WARN hiện tại | Initial schema snapshot0lints; sau Auth fixtures có leaked-password protection disabled. Pro+ feature; Free plan, không đổi settings hoặc mua |
| Performance advisors | INFO follow-up |2FK thiếu covering index: blocks.blocked_id/candidate_references.peer_id;31unused indexes trên schema mới; chưa thêm/xóa DDL |
| Real Auth fixtures | PASS provisioning/login | User tạo2accounts Dashboard/Auto confirm; helper login/getUser/revoke validation session; no Admin key |
| Hosted browser journey | PASS scoped | Login/consent/owner/mood/memory/matching/races/realtime/restart/reveal/report/block/provider revoke/logout replay;1core+1Nhịp case PASS; model fake |
| Public signup/email delivery/recovery | NOT TESTED | Admin-confirmed fixtures không chứng nhận SMTP/signup/recovery; UI hiện có login |
| Live AI/STT | BLOCKED | Account privacy/budget chưa cho phép; usage0; SDK fake model riêng trong harness |

Initialization SHA256 `90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0` và runtime template SHA256 `d9124bfd7747a7a04841b8e471a38ddfe6de04d87f91b20ffd63e3f79a1f0461` đều đã duyệt và commit. Không chạy lại initializer/role creation. Supabase migration history riêng trống vì nguồn revision là Alembic, không qua MCP migrations.

Runtime probe đầu42501 do diagnostic query dùng tên Auth relation; sửa catalog OID đã PASS, không thêm grants hoặc replay DDL. Failure artifact giữ nguyên; [verification chỉ đọc](supabase-runtime-verification.json) ghi trạng thái hiện tại. [Checkpoint đầu](supabase-e2e-attempt-1.json) chứng minh teen gate/consent mặc định trong lần đầu fixture chưa onboarding.

[Final hosted checkpoints](supabase-e2e-checkpoints.json), [Nhịp tool proof](supabase-scoped-tool-proof.json), [anonymous access denied406](supabase-public-access.json) và [post-E2E catalog/advisors](supabase-post-e2e-inspection.json). SQL/roles không có thêm quyền để làm test PASS.
