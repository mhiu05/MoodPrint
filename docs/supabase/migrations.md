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

[READY_REVISIONS](../../backend/app/core/revisions.py) hiện chỉ gồm **`0016_guest_foundation`**. Schema cũ thiếu cột lifecycle guest không được báo ready, để image cũ coi mọi user là registered không thể chạy trên schema mới. Không thay revision bằng stamp khi DDL chưa chạy.

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

Ưu tiên expand-only và rollback image nếu schema tương thích, nhưng phải kiểm tra `READY_REVISIONS` thực tế của image cũ. Downgrade destructive bị từ chối; không drop dữ liệu để rollback app. Restore cần rehearsal, tombstones, consent/session revocations và gates trước mở traffic. Physical backup retention và provider erasure là việc riêng, không được chứng minh bằng `alembic check`.
