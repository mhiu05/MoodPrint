# Release runbook

Xác minh trên `main` tại `2d00c8d2`, ngày 06/11/2026. Mô tả trong prompt được đối chiếu với repo; chỗ khác nhau ghi ở §9.

## 1. "Released" nghĩa là gì

Chỉ coi là xong khi đủ sáu điều:

1. Mọi WS trong phạm vi MVP đã vào `mhiu05/feat-refactor` qua PR; mỗi PR có CI `Verify local application` xanh.
2. PR `mhiu05/feat-refactor` → `main` có CI xanh và đã merge.
3. CI trên push vào `main` xanh, và `Publish verified staging release` thành công cho đúng SHA đó.
4. Poller trên EC2 đã triển khai `staging-<sha>`; `/api/v1/health/live` và `/api/v1/health/ready` trả OK.
5. Smoke trên staging bằng phiên khách mới và tài khoản trình bày: KB-A/B/C chạy được, có ảnh hoặc Playwright.
6. Có release note: SHA, migration đã áp, flag đã bật, giới hạn đã biết, cách rollback.

## 2. Pipeline thực tế

| Bước | Chi tiết | Nguồn |
| --- | --- | --- |
| CI | Workflow `Verify local application`, chạy trên mọi push và PR, khoảng 35 phút | `.github/workflows/verify.yml` |
| Trigger publish | `workflow_run` khi CI trên push vào `main` thành công | `deploy-staging.yml` |
| Dispatch tay | `release_sha` phải là `main` hiện tại; `approval` = `DEPLOY STAGING <sha>`; actor phải là chủ repo; nhánh `main` | `deploy-staging.yml` |
| Hold | `release_hold.py` kiểm tra `deploy/guest-experience.release-hold`; có file là chặn | **Hiện không có marker** |
| Validate | SHA đúng head `main`; CI run đúng workflow id `394882427`; `main` đổi thì bỏ qua | |
| Build | Hai image, kiểm tra không có secret, không có `.env`, không có source map | |
| Publish | GHCR theo digest, attestation, prerelease `staging-<sha>` | |
| Poller | systemd timer 5 phút, chạy `/opt/moodprint/poll_release.py` | `deploy/aws/` |
| Xác minh | Attestation của manifest và image, CI run, publish run, repo id `1430876891` | `poll_release.py` |
| Deploy | `deploy.sh`: đọc SSM `/moodprint/staging/runtime`, yêu cầu đúng một dòng `APP_ENV=production`, `compose up`, chờ `api`, `web`, `proactive`, `maps` healthy và `/ready` qua HTTPS | |
| Rollback tự động | Health lỗi: khôi phục image trước | `deploy.sh` |

**Quan trọng**

- `deploy.sh` **không** cập nhật `compose.staging.yml`, `Caddyfile`, `poll_release.py`, `deploy.sh`. Các file này chỉ đổi khi chạy lại `install-release-poller.sh` trên host. Thiết kế MVP không cần đổi chúng.
- Runtime đọc từ SSM lúc deploy. Đổi SSM không có hiệu lực tới lần deploy sau.
- `READY_REVISIONS` quyết định `/ready`. Giữ đúng theo `backend/app/core/revisions.py`.
- `/ready` kiểm tra `alembic_version` và helper `is_provider_session_active`.
- Không auto-migrate khi startup. Alembic online từ chối host remote.
- Hiện không có branch protection; xem [OD-09](../12-open-decisions.md#od-09--quy-tắc-merge).

## 3. Trạng thái đã biết

| Mục | Giá trị | Nhãn |
| --- | --- | --- |
| Hosted revision | `0029_journal_intelligence` | VERIFIED |
| Project Supabase | `roznanxbiyqybjpvtilq`, pooler `aws-0-ap-northeast-1` | VERIFIED trong script |
| Region AWS trong code | `ap-southeast-2` | INFERRED; xác nhận bên dưới |
| SSM parameter | `/moodprint/staging/runtime` | VERIFIED trong code |
| Domain | `moodprint.duckdns.org` | VERIFIED |
| Marker hold | Không có | VERIFIED |
| Model | `gpt-6-luna`, ngân sách 20 USD/ngày theo tài liệu 05/11/2026 | INFERRED |
| Supabase MCP | Chạy bằng role `postgres`, chủ bảng `moodprint`, có quyền CREATE | VERIFIED |
| AWS MCP | Owner xác nhận có. Phiên audit chưa kiểm chứng: `aws-mcp` timeout, `aws sts` trên máy audit exit 253 | UNKNOWN |
| `JOURNAL_STORAGE_KEY` trên staging | Chưa rõ | UNKNOWN, kiểm ở preflight |
| Cấu hình guest trên staging | Chưa rõ | UNKNOWN, kiểm ở preflight. Cần `GUEST_CAPTCHA_SITE_KEY`, `GUEST_ABUSE_HMAC_KEY` |
| Widget Turnstile | `MoodPrint Guest`, Invisible từ 06/11/2026, hostnames `127.0.0.1`, `localhost`, `moodprint.duckdns.org` | VERIFIED trên Cloudflare |
| CAPTCHA protection của Supabase | Cloudflare báo chưa thấy siteverify | UNKNOWN, kiểm ở preflight |

**Region**: xác nhận tại **AWS Settings > View all projects > Overview > Additional Info > Region**. Nếu không xác nhận được, xem `~/.aws/config`. Mọi tài nguyên Regional phải ở Region được chọn. MVP không tạo tài nguyên AWS mới. Nếu lệnh AWS đột nhiên trả "Access Denied", kiểm tra spend limit tại AWS Settings > Billing. Máy chủ MCP AWS không kết nối được trong phiên audit, nên phần này chưa đối chiếu với tài liệu AWS.

## 4. Vì sao thứ tự C → SQL → F đơn giản hơn lần 0029

Lần 0029 thêm cột vào bảng đang map nên cần tách tree. Lần này chỉ **thêm bảng** và **nới CHECK**. Image đang chạy đọc được schema mới, chỉ `READY_REVISIONS` không nhận. Vì vậy:

- **C** = `main` + `READY_REVISIONS = ("0029_journal_intelligence", "0035_support_practice")`, không có migration mới, không có ORM mới.
- **F** = `mhiu05/feat-refactor`, `READY_REVISIONS = ("0035_support_practice",)`.

## 5. Các bước

### Bước 0: điều kiện trước

- [ ] G0–G4 đạt, ghi trong ledger.
- [ ] OD-02 xong: có ít nhất 40 thẻ approved và template đã duyệt, `reviewed_by: mhiu05`.
- [ ] Supabase Authentication > Attack Protection: CAPTCHA bật, nhà cung cấp Turnstile, đúng secret của widget. Chưa bật thì báo owner, vì token không được kiểm tra.
- [ ] `main` CI xanh.
- [ ] Supabase MCP: `select version_num from moodprint.alembic_version` trả `0029_journal_intelligence`.
- [ ] AWS MCP: `aws sts get-caller-identity` thành công, không ghi Account hay ARN vào PR. Lỗi thì báo owner đăng nhập lại.
- [ ] Region khớp `ap-southeast-2`, xác nhận theo [OD-12](../12-open-decisions.md#od-12--credential).
- [ ] Đọc `/moodprint/staging/runtime` vào bộ nhớ, **chỉ in tên khóa**. Kiểm tra có `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_DAILY_BUDGET_USD`, `VOYAGE_API_KEY`, `JOURNAL_STORAGE_KEY`, `STT_MODEL`, và nhóm `GUEST_*`, `AUTH_CAPTCHA_ENABLED`. Thiếu `JOURNAL_STORAGE_KEY` hoặc `VOYAGE_API_KEY` thì báo owner.

### Bước 1: chuẩn bị SQL (trên nhánh)

```bash
# từ root, với backend/.venv
python scripts/apply_supabase_review.py --upgrade 0035
python scripts/check_reviewed_artifacts.py
```

Review-only không cần credential, không kết nối hosted. Ghi lại `sha256`.

### Bước 2: diễn tập

Dựng DB disposable có schema tương đương hosted. Có thể phục hồi snapshot chỉ cấu trúc do owner cung cấp; không sao chép dữ liệu người dùng. Tạo role `moodprint_runtime`, `moodprint_app` như hosted; xóa role sau khi xong vì role là cluster-wide.

```bash
python scripts/apply_supabase_review.py --upgrade 0035 --approved-sha256 <sha> --rehearse-url <local _test url>
```

Dùng cả image C: ASGI trả `/ready` 200 trên 0029 và 0035.

### Bước 3: image C

1. Từ `main`, nhánh `release/school-safety-c`.
2. Đổi `READY_REVISIONS`, sửa test ghim tuple.
3. PR vào `main`, CI xanh, merge.
4. Chờ Publish, chờ poller (tối đa khoảng 5 phút), kiểm tra:

```bash
gh run list --branch main --limit 3
curl -fsS https://moodprint.duckdns.org/api/v1/health/ready
gh release view staging-<sha>
```

Ghi lại digest API và web của C: đây là đích rollback.

### Bước 4: cấu hình SSM qua AWS MCP

Thêm vào `/moodprint/staging/runtime`, không xóa dòng có sẵn:

```text
APP_PROFILE=school_safety
OPENAI_MODEL=gpt-6-luna
AI_TIMEOUT_SECONDS=60
AI_DAILY_BUDGET_USD=20
TTS_PROVIDER=openai_realtime
TTS_MODEL=gpt-realtime-2.1-mini
TTS_VOICE=marin
STT_MODEL=gpt-transcribe
GUEST_AUTH_ENABLED=true
GUEST_PAID_ENABLED=true
GUEST_DAILY_BUDGET_USD=5
GUEST_PRICING_JSON=<theo WS-02-T12>
GUEST_AI_TURNS=200
GUEST_AI_PER_MINUTE=20
GUEST_VOICE_CLIPS=60
GUEST_VOICE_SECONDS=1800
GUEST_VOICE_PER_MINUTE=6
GUEST_AI_GLOBAL_CONCURRENCY=30
GUEST_VOICE_GLOBAL_CONCURRENCY=5
```

Cách làm: tải giá trị vào file tạm mode 600 hoặc bộ nhớ, chỉnh, `put-parameter --type SecureString --overwrite`, xóa file tạm. Ghi lại số version cũ để khôi phục. So tên khóa trước và sau. Không in giá trị.

C bỏ qua biến lạ (`extra="ignore"`), nên thêm trước là an toàn. Cấu hình chỉ có hiệu lực ở lần deploy tiếp theo.

### Bước 5: áp SQL hosted

**Đường chính: Supabase MCP.** Project `roznanxbiyqybjpvtilq`, role `postgres`.

1. Đếm hàng toàn bộ bảng `moodprint`, lưu làm mốc.
2. Đọc `deploy/supabase/reviewed-sql/0035-review.sql`, tính SHA-256, so với `MANIFEST.json`.
3. Gửi **nguyên văn** nội dung file qua `execute_sql`, một lần. Không sửa byte nào. File đã có `BEGIN`, `COMMIT`, cập nhật `alembic_version`.
4. Chạy kiểm tra:

```sql
select version_num from moodprint.alembic_version;

select c.relname, c.relrowsecurity
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'moodprint' and c.relname = any(:new_tables);

select tablename, policyname, roles from pg_policies
where schemaname = 'moodprint' and tablename = any(:new_tables);

select t, has_table_privilege('moodprint_app', 'moodprint.' || t, 'SELECT,INSERT,UPDATE,DELETE') as runtime_dml,
       has_table_privilege('anon', 'moodprint.' || t, 'SELECT') as anon_select,
       has_table_privilege('authenticated', 'moodprint.' || t, 'SELECT') as auth_select
from unnest(:new_tables) t;

select has_schema_privilege('moodprint_app', 'moodprint', 'CREATE');
```

Kỳ vọng: revision `0035_support_practice`; 18 bảng có RLS và policy `backend_access`; runtime có DML; `anon`, `authenticated` không có quyền; runtime không CREATE; số hàng bảng cũ không đổi. `:new_tables` là 18 bảng ở [05](../05-data-model-and-migrations.md).

5. Ghi `deploy/supabase/reports/0035-execution.json` theo định dạng report của script: sha256, thời điểm, từng kiểm tra, không có thông tin nhận dạng.

**Không** dùng `apply_migration` của MCP: nó ghi vào lịch sử migration của Supabase, còn nguồn sự thật ở đây là Alembic. Không chạy `alembic upgrade` lên hosted.

**Nếu `execute_sql` không chạy được nguyên văn** (ví dụ từ chối điều khiển giao dịch): dừng. Không tách câu lệnh, không sửa file. Báo owner để cấp `DATABASE_MIGRATION_URL`, rồi chạy `python scripts/apply_supabase_review.py --upgrade 0035 --apply --approved-sha256 <sha>` với credential trong environment.

Sau đó: `/ready` phải vẫn 200 trên C.

### Bước 6: image F

1. Merge `main` vào `mhiu05/feat-refactor`, sửa conflict, chạy lại kiểm tra.
2. `READY_REVISIONS = ("0035_support_practice",)`.
3. PR vào `main`, CI xanh, merge. Không merge thứ khác trong lúc này.
4. Chờ Publish, poller, `deploy.sh`.
5. Kiểm tra health và log.

### Bước 7: KB và tài khoản trình bày

Worker tự sync KB sau khởi động. Kiểm tra `select count(*) from moodprint.kb_cards where review_status='approved'`.

Tạo một tài khoản trình bày bằng `scripts/provision_auth_test_accounts.py` hoặc Supabase dashboard. Đăng nhập, xác nhận điều khoản, nhập hồ sơ "Nhóm chat lớp" của `kb-a` qua giao diện. Giao mật khẩu cho owner qua kênh riêng, không qua PR.

### Bước 8: smoke

Theo [kịch bản](../demo/scenarios-KB-A-B-C.md) và [tình huống mẫu](../demo/showcase-cases.md), với **model thật**, bằng phiên khách mới và tài khoản trình bày. Ca xác suất chạy 3 lần. Thêm:

- `POST /auth/signup` trả 403.
- `/quyen-rieng-tu` mở được, có câu dẫn chiếu Turnstile Privacy Addendum.
- Route denylist trả 404.
- Tài khoản 18+ không vào được app.
- `/ho-tro` mở được khi chưa đăng nhập.
- Không có nội dung tin nhắn trong log: `journalctl`, `docker logs`.
- Ghi chi phí smoke vào release note. Không tính vào trần eval live.
- Xác nhận `ai_usage.model` là `gpt-6-luna`, TTS phát được trên điện thoại thật.
- Luồng khách chạy tay bằng trình duyệt thật: CAPTCHA từng chặn trình duyệt tự động. Từ trang chủ tới tin đầu tiên không có bước xác minh. Sau hạn, dữ liệu khách không còn.

### Bước 9: release note

Ghi `docs/moodprint-school-safety/evidence/release.md`.



## 6. Rollback

| Tình huống | Hành động |
| --- | --- |
| Health F fail khi deploy | `deploy.sh` tự khôi phục C. Kiểm tra log, báo owner |
| Smoke fail sau khi F đã healthy | Chạy SSM document `ssm-document.json` với `apiImage`, `webImage` của C (digest), `releaseSha` của C. Không đổi schema. Báo owner kèm chẩn đoán |
| Poller sẽ deploy lại F? | Poller so `main` với state; sau rollback tay, tạm dừng timer hoặc đẩy bản sửa. Hỏi owner |
| SQL fail | Giao dịch tự rollback; revision giữ 0029; C vẫn chạy |
| Cần quay về bản cũ | Khôi phục version SSM cũ, deploy lại |

**Không** downgrade schema trên hosted. Không chạy `DROP`, `TRUNCATE`. Trên hệ thống có rollback image, luôn xác nhận `READY_REVISIONS` của image đó nhận revision hiện tại.

## 7. Giới hạn của Grok

Theo §8.3 của prompt: không push thẳng hay force-push `main`; không tắt, skip, nới CI; không xóa test; không đưa secret vào code, log, commit, PR; không phá dữ liệu hosted; không gửi đường dẫn staging cho học sinh hay trường học.

Dừng và hỏi owner khi: cần credential chưa có; CI đỏ sau 3 lần thử theo 3 hướng; gate không đạt; gặp mục chưa trả lời trong [12-open-decisions](../12-open-decisions.md).

## 8. Marker release hold

Trên `main` hiện **không có** `deploy/guest-experience.release-hold`. Lần gỡ cuối thuộc commit `fe4cee6c` trong PR #40. Không cần gỡ.

Nếu ai đó thêm lại marker: Publish bị bỏ qua, CI vẫn chạy. Điều kiện gỡ theo `deploy/aws/README.md`: PR riêng được owner duyệt, sau khi schema hosted, các quyết định và điều kiện thủ công đã xong. Có thể chủ động dùng marker này để giữ release trong lúc chuẩn bị F, nhưng thứ tự ở §5 không cần.

## 9. Chỗ repo khác mô tả trong prompt

| Prompt | Repo |
| --- | --- |
| Nhánh `feat/refactor` | `mhiu05/feat-refactor`, owner đã chốt |
| Có thể có marker hold | Không có |
| Workflow chạy trên push `main` | Đúng, thêm điều kiện `main` không đổi trong suốt quá trình |
| `workflow_dispatch` có approval | Đúng, thêm điều kiện actor là chủ repo |
| CI xanh là tiền đề | **Hiện đỏ** ở hai commit gần nhất. Sửa ở WS-01-T01 |
| Runtime grants | Migration cấp qua `protect(table)`, không có bước riêng |
| Áp SQL bằng `apply_supabase_review.py --apply` | Vẫn dùng được nếu có DSN. Đường chính là Supabase MCP theo chốt của owner |
