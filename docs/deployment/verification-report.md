# Báo cáo xác minh — 25/10/2026 (Asia/Bangkok)

**Trạng thái: PARTIAL / HOLD cho staging release.** Các kết quả local bên dưới ghi lại lần xác minh trước và không chứng minh deployment live. AWS staging infrastructure đã tồn tại; app containers chưa được triển khai. Pipeline GHCR và EC2 poller đang ở PR #1 draft/open. Không dùng PASS để chỉ một deployment chưa xảy ra.

| Phạm vi | Lệnh/bằng chứng thực thi | Kết quả |
| --- | --- | --- |
| Baseline | `git status --short`; kiểm tra README/manifests/CI/config/migrations | Historical baseline: ghi nhận thay đổi tracked/untracked tại thời điểm đó; không reset/clean. Deployment changes hiện được review trên PR #1. |
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
| Workflow/scripts | `actionlint:1.7.12` qua Docker; `bash -n` và ShellCheck hai script; Ruff các script SSE/DB; parse JSON IAM/SSM/CloudWatch | PASS: static syntax đã chạy trước bản poller hiện tại. CI hiện tại cần xác minh workflow, tests và production image build; AWS/IAM thật và rollback chưa được chạy. |
| Dependencies | `npm.cmd audit --audit-level=low` | PASS: 0 vulnerabilities tại thời điểm lệnh. Container CVE scan chưa chạy. |
| Paid provider guard | `uv run --locked python ../scripts/smoke_providers.py --provider openai` không có flags | PASS: từ chối request; paid OpenAI/Voyage/STT live **NOT RUN**. |
| AWS/remote | Lần xác minh local ban đầu không provision, ECR push, SSM Run Command hay Supabase remote DDL | Từ lần đó, kiểm tra AWS Console xác nhận EC2/EIP/SSM/role/Standard SecureString đã có. Chưa có app container, GHCR release, SSM deploy hoặc remote migration. Cần cài poller và cấu hình quyền runtime trước khi deploy. |

## Điểm chặn trước staging

1. PR #1 vẫn draft/open. CI mới nhất của nhánh phải thành công trên SHA cuối; chỉ merge sau khi quyền runtime EC2 và cách truy cập GHCR đã được chọn/cấu hình. Giữ branch protection nếu push lên main cần review.
2. Supabase read-only checks saw revision 0010 and helper executable; backup/restore and privilege review remain. No remote DDL has been run.
3. Cấp cho EC2 đúng quyền `ssm:GetParameter` trên `/moodprint/staging/runtime`, cài systemd poller, và cấu hình truy cập GHCR private/public. Giữ AWS Free Plan, spending limits, ECR repositories và IP hiện có.
4. Kết nối trình duyệt tới `https://moodprint.duckdns.org` bị từ chối; DNS lookup từ workspace này không hoạt động. TLS, frontend, backend readiness và application version vì vậy NOT TESTED.
5. Auth, mood tracking, matching, messaging, AI, memory, Voyage và STT vẫn NOT TESTED trên host live. Không bật paid provider calls trước khi review cấu hình, consent, ngân sách và synthetic smoke tests.
6. Chưa xác minh CI lỗi không deploy, detection release của main mới nhất, deployment delay tự động tới EC2, hoặc rollback live.

**Xác nhận:** Lần local verification ban đầu không tạo resource AWS, không push ECR và không chạy remote migration. Trong lần tiếp tục này, chỉ có code/docs thay đổi trên draft branch; không tạo thêm AWS resource, không chạy remote migration, không đổi dữ liệu production, và không gửi OpenAI/Voyage requests trả phí.
