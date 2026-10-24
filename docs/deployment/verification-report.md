# Báo cáo xác minh local — 25/10/2026 (Asia/Bangkok)

**Trạng thái: PARTIAL / HOLD cho staging release.** Phần chuẩn bị local đã có image, proxy, Compose, CI/CD có gate và runbook. Chưa có AWS resource, domain/TLS thật, GitHub environment reviewer, thao tác migration remote trong task này hay live provider smoke. Không dùng PASS để chỉ một deployment chưa xảy ra.

| Phạm vi | Lệnh/bằng chứng thực thi | Kết quả |
| --- | --- | --- |
| Baseline | `git status --short`; kiểm tra README/manifests/CI/config/migrations | PASS: ghi nhận nhiều tracked/untracked changes trước task, giữ nguyên `.gitignore`; không reset/clean/commit. |
| Frontend | `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | PASS: typecheck, 86 Vitest tests, Vite production build. |
| Browser | `npm.cmd run test:e2e -- --reporter=line --output=$env:TEMP\moodprint-staging-e2e` | PASS: 34 Playwright tests; nhiều API được route-fulfill, không phải backend/proxy live. Reporter và artifacts ra ngoài repo để không ghi đè evidence của người dùng. |
| Backend | `uv run --locked ruff check app tests evals ../scripts/smoke_providers.py`; `uv run --locked mypy app` | PASS. Baseline Ruff trước sửa có một unused `UUID` import trong `evals/scenarios_live.py`; đã bỏ import, không đổi hành vi. |
| Backend + DB | `uv run --locked pytest -q` với `TEST_DATABASE_URL` trỏ PostgreSQL pgvector disposable tên `_test` | PASS: 246 tests, không skip, 228,71 giây. Lần baseline không DB: 119 pass/122 skip trước khi thêm test cấu hình. |
| Migration local | `alembic upgrade head`, `alembic check`, query `moodprint.alembic_version` trên disposable DB | PASS: `0010_account_deletion`, không có upgrade operations mới. Không đụng Supabase remote. |
| Supabase read-only | `scripts.inspect_database.inspect()` qua hai URL cấu hình, chỉ in status/revision/boolean metadata | PASS: cả runtime và migration URL kết nối đúng project, TLS `require`, revision `0010_account_deletion`, private Auth bridge executable cho runtime. Runtime role direct `auth.sessions` SELECT=false đúng ranh giới helper. Không chạy DDL. |
| Docker | `docker build --platform linux/amd64 -t moodprint-api:ci backend`; `docker build --platform linux/amd64 -t moodprint-web:local frontend` | PASS: backend multi-stage Python 3.12 và frontend Node22/Caddy; API image UID10001. |
| Compose/proxy/SSE | `docker compose -f deploy/compose.staging.yml config -q`; `caddy validate`; Git Bash `scripts/test_staging_proxy.sh` | PASS: `/` 200, `/auth/callback` 200, `/api/v1/health/live` 200, `/ready` 503 đúng khi DB cố ý vắng, `/session` 401; sự kiện SSE đầu tới trước sự kiện thứ hai. Không cần Vite dev proxy. |
| Container shutdown | Chạy backend image, đợi Docker health = `healthy`, rồi `docker stop --time 30`; đo thời gian và exit code | PASS: dừng sau 0,73 giây, exit 0. Một thử nghiệm dừng ngay 2 giây sau tạo container hết giới hạn 10 giây; cần dùng health gate trước khi đánh giá graceful shutdown. Compose dành 150 giây cho các lượt đang xử lý; chưa thử tải AI đang chạy. |
| Secret/log check | Kiểm image không có `/srv/moodprint/.env` và `/srv/*.map`; request Cookie/Authorization/query synthetic gây upstream 502 rồi xem Caddy log | PASS: không thấy sentinel synthetic trong log; không có `.env`/source map trong image. Không khẳng định đã quét toàn bộ secret của mọi file. |
| Workflow/scripts | `actionlint:1.7.12` qua Docker; `bash -n` và ShellCheck hai script; Ruff các script SSE/DB; parse JSON IAM/SSM/CloudWatch | PASS: static syntax. SSM/IAM thật và rollback chưa được chạy. |
| Dependencies | `npm.cmd audit --audit-level=low` | PASS: 0 vulnerabilities tại thời điểm lệnh. Container CVE scan chưa chạy. |
| Paid provider guard | `uv run --locked python ../scripts/smoke_providers.py --provider openai` không có flags | PASS: từ chối request; paid OpenAI/Voyage/STT live **NOT RUN**. |
| AWS/remote | Không có lệnh provision, ECR push, SSM Run Command, Supabase remote DDL | BLOCKED/NOT RUN: cần duyệt riêng và hạ tầng. |

## Điểm chặn trước staging

1. Commit và review một snapshot chứa cả migration 0006–0010 và các file triển khai; hiện file migration/user work còn uncommitted/untracked. Chạy CI push của đúng SHA rồi thiết lập GitHub environment `staging` với required reviewer; API GitHub hiện trả `[]` environments.
2. Supabase read-only đã xác nhận revision 0010 và helper executable; còn backup + restore drill, SQL/DDL và quyền account-deletion review riêng. Không bật accounting/history/semantic memory chỉ từ metadata revision.
3. Duyệt dự toán, IAM trust subject thực, ECR immutable, SSM document/agent, domain, EC2 x86_64, security group, SecretString/KMS, CloudWatch. Chưa có tài nguyên nào để chứng minh HTTPS/TLS/rollback/monitoring.
4. `STT_MODEL=gpt-transcribe` trong env mẫu cũ chưa có trong transcription API reference hiện hành; giữ STT tắt đến khi chọn model có quyền truy cập và smoke synthetic được duyệt. Live OpenAI/Voyage đều chưa xác nhận auth/quota/region/retention của tài khoản.
5. Context AI tạm trong RAM mất khi restart; không chạy hơn một worker/replica. Khoảng 50 người cần bài đo concurrency, Supabase pool và provider quota sau khi có staging. Container CVE scan và restore drill chưa thực hiện.

**Xác nhận:** Không tạo resource AWS, không push ECR, không chạy remote migration, không đổi dữ liệu production, không commit/push, không gửi request OpenAI/Voyage trả phí.
