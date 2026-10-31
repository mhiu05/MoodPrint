# Migration và SQL review

## Chuỗi hiện tại

Nguồn: [backend/alembic/versions](../../backend/alembic/versions/). Revision ID là chuỗi đầy đủ, không chỉ số file.

| Revision | Thay đổi chính |
| --- | --- |
| `0001_foundation` | Schema/bảng nền tảng cá nhân, AI metadata và social |
| `0002_safety` | Identity reveal và reports |
| `0003_lifecycle` | Data lifecycle jobs |
| `0004_eligibility` | Khai báo tuổi/eligibility |
| `0005_export_scope` | Export scope capacity |
| `0006_ai_usage` | AI usage/accounting |
| `0007_chat_history` | AI preferences, persistent conversation/messages và turn coordination |
| `0008_memory_proposals` | Proposal persistence |
| `0009_memory_embeddings` | pgvector jobs/index |
| `0010_account_deletion` | Account deletion/provider identity helper |
| `0011_social_stabilization` | Social/read state và các bổ sung ổn định |
| `0012_matching_v2` | Profile/ranking support, daily matching counters |
| `0013_shared_activities` | Activity sessions/participants/responses |
| `0014_moderation` | Staff role/action và enforcement support |
| `0015_context_privacy` | Turn context policy boundary |
| `0016_guest_foundation` | Guest trial: `users.account_kind`/deadline bất biến, session cap, bảng provisioning/cleanup/usage/abuse và budget không gắn identity (chưa có approved hosted SQL; xem GE-14.3) |
| `0017_guest_security` | Helper `is_provider_session_active` guest-aware: đồng hồ database tươi (VOLATILE), `is_anonymous` provider khớp `account_kind`, deadline T (chưa có approved hosted SQL) |
| `0018_app_feedback` | Feedback không gắn danh tính (`app_feedback`, receipt tạm, audit review), hai hàm validator private, thêm scope `feedback_attempt` cho bucket HMAC; RLS + chỉ `moodprint_runtime` |
| `0019_journal` | Ba bảng journal cộng thêm (`journal_entries`, `journal_media`, `journal_storage_deletions`), RLS và grant chỉ cho `moodprint_runtime`; không sửa dòng Mood cũ |
| `0020_private_profile_retirement` | Xóa dữ liệu `private_items` và đề xuất riêng tư; giữ ghi nhớ AI đã duyệt, bỏ liên kết nguồn đã nghỉ |

[READY_REVISIONS](../../backend/app/core/revisions.py) hiện chỉ gồm **`0020_private_profile_retirement`**. Image trước revision này không còn được xem là tương thích vì source/purpose fields và bảng private items đã bị xóa. Mọi head trước 0020 bị từ chối. Không thay revision bằng stamp khi DDL chưa chạy.

## Local disposable verification

Tạo database riêng, ví dụ container tài liệu ở cổng 15432:

```powershell
# repository root; container này chỉ phục vụ test và dùng mật khẩu local công khai
docker exec moodprint-docs-db-20261028 createdb -U postgres moodprint_migration_test
Push-Location backend
$env:DATABASE_URL=''
$env:DATABASE_MIGRATION_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:15432/moodprint_migration_test'
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
Pop-Location
```

Tên container/port phụ thuộc môi trường bạn đã tạo; xem [development](../development.md). `alembic check` phải báo không còn upgrade operation mới; revision hiện tại phải khớp head. Không chạy pytest reset trên database dùng kiểm tra migration này.

[env.py](../../backend/alembic/env.py) chỉ cho online migration đến `localhost`, `127.0.0.1`, `::1`, `database`; từ chối remote. Offline export sinh SQL không kết nối database. Local bootstrap cài provider-session helper, không provision Supabase Auth thật.

## Hosted workflow

1. Xác nhận project/host/database/role/TLS và revision hiện tại bằng đường đọc được phép.
2. Tạo SQL từ đúng Alembic range; review schema, ownership, grants, extension, helper và compatibility.
3. So sánh SQL/hash/bytes với artifact được review trong `deploy/supabase/reviewed-sql/MANIFEST.json`.
4. Lấy chấp thuận cụ thể cho target và artifact trước DDL. Manifest ghi nhận artifact, không tự cấp quyền thực thi.
5. Dùng operational script hỗ trợ đúng revision; apply từng bước, kiểm tra revision/grants/helper/readiness và lưu report an toàn.

`scripts/apply_supabase_review.py` hiện có initialization và upgrade plans đến **0014**. **0015 chưa có approved upgrade plan trong script/manifest hiện tại.** Trước hosted upgrade 0015 cần bổ sung review artifact/plan và approval; không chạy `alembic upgrade head` để bypass remote guard. Sự tồn tại của local migration không đồng nghĩa hosted path đã được review.

Kiểm tra integrity offline từ root:

```powershell
uv run --project backend --locked python scripts/check_reviewed_artifacts.py
```

Không sửa newline/bytes SQL đã pin để format tài liệu. `.gitattributes` bảo toàn SQL hash trên Windows. Report generated nằm trong `deploy/supabase/reports/`, tránh đưa secret/execution data vào commit.

## Rollback và restore

Guest head là **0018_app_feedback**. Range 0015→0018 có [pending review package](../guest-experience/implementation/evidence/release-readiness.md): sinh offline bằng `prepare_guest_migration_review.py`, rehearsal rollback trên DB local rỗng bằng `verify_guest_migration_review.py`. Không ghi đè initialization SQL/MANIFEST. Hosted apply từ revision thực tế (kể cả 0014→0015 nếu còn thiếu) cần artifact, target và chấp thuận riêng. Rollback giữ guest guards/cleanup.

Ưu tiên expand-only và rollback image nếu schema tương thích, nhưng phải kiểm tra `READY_REVISIONS` thực tế của image cũ. Downgrade destructive bị từ chối; không drop dữ liệu để rollback app. Restore cần rehearsal, tombstones, consent/session revocations và gates trước mở traffic. Physical backup retention và provider erasure là việc riêng, không được chứng minh bằng `alembic check`.
