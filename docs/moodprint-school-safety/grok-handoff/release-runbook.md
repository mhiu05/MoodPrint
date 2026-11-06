# Release runbook

Xác minh trên `main` tại `2d00c8d2`, ngày 06/11/2026. Mô tả trong prompt được đối chiếu với repo; chỗ khác nhau ghi ở §9.

## 1. "Released" nghĩa là gì

Chỉ coi là xong khi đủ sáu điều:

1. Mọi WS trong phạm vi MVP đã vào `mhiu05/feat-refactor` qua PR; mỗi PR có CI `Verify local application` xanh.
2. PR `mhiu05/feat-refactor` → `main` có CI xanh và đã merge.
3. CI trên push vào `main` xanh, và `Publish verified staging release` thành công cho đúng SHA đó.
4. Poller trên EC2 đã triển khai `staging-<sha>`; `/api/v1/health/live` và `/api/v1/health/ready` trả OK.
5. Smoke trên staging bằng tài khoản demo: KB-A/B/C chạy được, có ảnh hoặc Playwright.
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
- Hiện không có branch protection; xem [OD-09](../12-open-decisions.md#od-09--branch-protection).

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
| `JOURNAL_STORAGE_KEY` trên staging | Chưa rõ | UNKNOWN |
| Cấu hình guest trên staging | Chưa rõ | UNKNOWN |

**Region**: xác nhận tại **AWS Settings > View all projects > Overview > Additional Info > Region**. Nếu không xác nhận được, xem `~/.aws/config`. Mọi tài nguyên Regional phải ở Region được chọn. MVP không tạo tài nguyên AWS mới. Nếu lệnh AWS đột nhiên trả "Access Denied", kiểm tra spend limit tại AWS Settings > Billing. Máy chủ MCP AWS không kết nối được trong phiên audit, nên phần này chưa đối chiếu với tài liệu AWS.

## 4. Vì sao thứ tự C → SQL → F đơn giản hơn lần 0029

Lần 0029 thêm cột vào bảng đang map nên cần tách tree. Lần này chỉ **thêm bảng** và **nới CHECK**. Image đang chạy đọc được schema mới, chỉ `READY_REVISIONS` không nhận. Vì vậy:

- **C** = `main` + `READY_REVISIONS = ("0029_journal_intelligence", "0035_support_practice")`, không có migration mới, không có ORM mới.
- **F** = `mhiu05/feat-refactor`, `READY_REVISIONS = ("0035_support_practice",)`.

## 5. Các bước

### Bước 0: điều kiện trước

- [ ] G0–G4 đạt, ghi trong ledger.
- [ ] OD-01, OD-05, OD-12 đã trả lời. OD-02 xong: có thẻ approved và template đã duyệt.
- [ ] `main` CI xanh.
- [ ] Hỏi owner xem có chuyện gì đang chạy trên staging không.

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

### Bước 4: cấu hình SSM (owner, hoặc Grok nếu được cấp quyền)

Thêm vào `/moodprint/staging/runtime`, không xóa dòng có sẵn:

```text
APP_PROFILE=school_safety_demo
AI_TIMEOUT_SECONDS=45
AI_DAILY_BUDGET_USD=20
TTS_PROVIDER=<theo OD-04>
TTS_API_KEY=<secret>
TTS_VOICE=<theo bake-off>
STT_MODEL=gpt-transcribe
```

C bỏ qua biến lạ (`extra="ignore"`), nên thêm trước là an toàn. Không in giá trị. Không gửi qua chat.

### Bước 5: áp SQL hosted

Credential qua environment của process, không qua command line, không đọc `backend/.env`:

```bash
# Đặt DATABASE_MIGRATION_URL, SUPABASE_URL trong environment
python scripts/apply_supabase_review.py --upgrade 0035 --apply --approved-sha256 <sha>
```

Script kiểm tra project, endpoint, owner, TLS; chạy trong một giao dịch; kiểm tra revision, số hàng, RLS, policy, DML, quyền API role; ghi report vào `deploy/supabase/reports/0035-execution.json`.

Sau đó: `/ready` phải vẫn 200 trên C.

Không chạy `alembic upgrade` lên hosted. Không dùng MCP `apply_migration`. Lấy lệnh `select version_num from moodprint.alembic_version` để kiểm tra.

### Bước 6: image F

1. Merge `main` vào `mhiu05/feat-refactor`, sửa conflict, chạy lại kiểm tra.
2. `READY_REVISIONS = ("0035_support_practice",)`.
3. PR vào `main`, CI xanh, merge. Không merge thứ khác trong lúc này.
4. Chờ Publish, poller, `deploy.sh`.
5. Kiểm tra health và log.

### Bước 7: seed và KB

```bash
# Đặt Auth Admin key trong environment
python scripts/seed_school_demo.py --apply --credentials-file <path mode 600>
```

Worker tự sync KB sau khởi động. Kiểm tra `select count(*) from moodprint.kb_cards where review_status='approved'`.

### Bước 8: smoke

Theo [kịch bản](../demo/scenarios-KB-A-B-C.md). Thêm:

- `POST /auth/signup` trả 403.
- Route denylist trả 404.
- Tài khoản 18+ không vào được app.
- `/ho-tro` mở được khi chưa đăng nhập.
- Không có nội dung tin nhắn trong log: `journalctl`, `docker logs`.
- Smoke chi phí nằm trong trần OD-11.

### Bước 9: release note

Ghi `docs/moodprint-school-safety/evidence/release.md`.

## 6. Rollback

| Tình huống | Hành động |
| --- | --- |
| Health F fail khi deploy | `deploy.sh` tự khôi phục C. Kiểm tra log, báo owner |
| Smoke fail sau khi F đã healthy | Chạy SSM document `ssm-document.json` với `apiImage`, `webImage` của C (digest), `releaseSha` của C. Không đổi schema. Báo owner kèm chẩn đoán |
| Poller sẽ deploy lại F? | Poller so `main` với state; sau rollback tay, tạm dừng timer hoặc đẩy bản sửa. Hỏi owner |
| SQL fail | Giao dịch tự rollback; revision giữ 0029; C vẫn chạy |
| Cần tắt demo | Bỏ `APP_PROFILE` trong SSM, deploy lại |

**Không** downgrade schema trên hosted. Không chạy `DROP`, `TRUNCATE`. Trên hệ thống có rollback image, luôn xác nhận `READY_REVISIONS` của image đó nhận revision hiện tại.

## 7. Giới hạn của Grok

Theo §8.3 của prompt: không push thẳng hay force-push `main`; không tắt, skip, nới CI; không xóa test; không đưa secret vào code, log, commit, PR; không phá dữ liệu hosted; staging không mở cho người dùng thật.

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
