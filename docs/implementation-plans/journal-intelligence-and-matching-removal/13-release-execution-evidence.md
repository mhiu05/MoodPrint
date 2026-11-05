# 13 — Bằng chứng thực thi release JI-51

Phiên bắt đầu ngày 05/11/2026, múi giờ Asia/Bangkok. Ủy quyền: prompt release
được chủ dự án gửi trong chat; trần chi phí phát sinh 1 USD. Không suy quyền từ
prompt cũ hoặc tài liệu lịch sử. Không đọc `E:\MoodPrint\backend\.env`.

## Trạng thái hiện tại

**Chưa release.** Đã xác minh hosted bằng SSM chỉ đọc; chưa thay đổi runtime,
chưa bật maintenance, chưa dừng poller hoặc áp SQL. Hosted vẫn là source
`d6280561a12cf50069ded12422734afb8c5e7335`, revision `0028_collaboration_defaults`.
Blocker: chưa có credential owner DB qua kênh được phép. Chi phí provider do
phiên khởi tạo: 0 USD (chưa gọi provider, chưa rollout).

Chỉ dẫn bổ sung trong chat sau preflight: chủ dự án bỏ yêu cầu backup và yêu cầu
release code mới nhất, cấp quyền tiếp tục. Backup không còn là điều kiện bắt buộc
của phiên này. Chỉ dẫn đó không cung cấp credential owner, không thay target/hash
SQL đã duyệt và không làm ORM F tương thích schema0028. Không suy ra quyền đọc
file `.env` bị cấm hoặc bypass kiểm tra readiness.

## Preflight

| Thời gian (UTC+7) | Thao tác / bằng chứng | Kết quả |
| --- | --- | --- |
| 05/11, trước 08:34 | `git status --short`; kiểm worktree/branch | Giữ nguyên thay đổi riêng `.gitignore`, prompt09, frontend evidence và các thư mục untracked; không stage/stash |
| 05/11 08:25 | `git fetch origin main`; kiểm SHA/tree | Main `b5bfefe5a31f6cf6af17b60d6aecbd011da97bf9`, tree `dd039d903284700812b2cb0e28f91b99184e7dbe` đúng bàn giao |
| 05/11 08:26 | Tạo worktree `E:\MoodPrint-release-ji51`, branch `release/ji51-preflight` | Worktree sạch từ origin/main; pin F bằng branch `release/ji51-feature-snapshot` tại cùng SHA |
| 05/11 08:34 | `gh run view 41872039771`; `gh pr view 38` | [Verify main](https://github.com/mhiu05/MoodPrint/actions/runs/41872039771) completed/success, event push, đúng SHA; [PR38](https://github.com/mhiu05/MoodPrint/pull/38) MERGED |
| 05/11 08:27–08:32 | GitHub connector và `gh api` chỉ chọn metadata quyền | Connector read-only; gh owner/admin/push hợp lệ; không đổi quyền |
| 05/11 08:30–08:32 | `aws sts get-caller-identity` qua subprocess kín, thử hai profile hiện hữu | Cả hai expired; không in account/ARN/credential; AWS CLI 2.38.5 |
| 05/11 08:32–08:35 | Chủ dự án xác nhận riêng chạy `aws login`; kiểm STS sau login | Login exit0, identity hợp lệ; không in account/ARN/output xác thực |
| 05/11 08:35–08:37 | EC2 metadata + DNS đối chiếu; SSM metadata | Một host running khớp DNS public và SSM Online; domain/repo/runtime parameter đúng môi trường |
| 05/11 08:36–08:37 | SSM: chỉ chọn metadata staging state, service health, revision và key booleans | Source0028 đúng baseline; bốn service healthy/running, restart0; homepage/live/ready200; gate tắt, không có backup gate; timer active/waiting/enabled |
| 05/11 08:37–08:38 | Kiểm kín credential channel trong runtime SSM và environment local | Không có DATABASE_MIGRATION_URL/owner credential; SSM chỉ có parameter runtime; không có credential backup riêng |
| 05/11 08:40 | Review-only0029 với approved hash; checker integrity | Offline export khớp, 7488bytes/hash nguyên vẹn; 12pinned/12consumed |

## Rulings và phụ thuộc

- Dùng worktree ngoài repo để bảo toàn working tree của chủ dự án và không sửa
  `.gitignore`. Không cài/nâng dependency hoặc sửa lockfile.
- JI-00→JI-50 là lịch sử; không làm lại. Các test mới chỉ phục vụ sửa an toàn
  release. Publication hold được giữ cho đến khi đủ điều kiện vận hành C.
- Hai nhánh `--apply` đã sửa thành `_env_file=None` cho cả initialization và
  incremental upgrade. Test chặn source dotenv trước khi tạo Settings, kể cả lượt
  RED. Giữ nguyên target/hash/TLS/transaction checks.
- C→rehearsal→0029→F là phụ thuộc tuần tự còn lại sau khi chủ dự án bỏ backup.
  Không phát hành C khi chưa có đường hoàn thành migration và khôi phục F.
  Không bật worker mới khi chưa chứng
  minh được trần chi phí toàn rollout.

## Kiểm thử phiên này

| Command / phạm vi | Kết quả thật |
| --- | --- |
| `pytest -q tests/test_reviewed_artifacts.py -k hosted_apply_uses --tb=short` trước sửa | RED: 2failed/28deselected/1,03s, đúng AssertionError trước dotenv filesystem access |
| Cùng command sau sửa hai constructor | GREEN: 2passed/28deselected/0,27s |
| `ruff check tests/test_reviewed_artifacts.py ../scripts/apply_supabase_review.py` | PASS |
| Hai file reviewed-artifacts/database-operations, chưa có disposable | 44passed/1skipped/22,94s; skip là integration SQL thiếu TEST_DATABASE_URL, không coi integration đạt |
| Disposable do phiên tạo | PostgreSQL17.10/pgvector0.8.2, loopback36435; container ownership label hợp lệ; không dùng dữ liệu hosted |
| `pytest -q tests/test_reviewed_artifacts.py tests/test_database_operations.py --tb=short --junitxml=<private-ops>/regression.xml` với disposable | **45passed/0failed/0skipped/47,35s**, runner49,406s; gồm SQL nguyên văn/roles/RLS và transaction rollback; không phải rehearsal snapshot hosted |
| Probe synthetic `run_upgrade` với connection không TLS | PASS: từ chối trước SQL, ddlSubmitted=false/transactionOutcome=not_submitted; không network |
| `check_docs.py` | PASS:182Markdown/1164links/144operations/130settings/64tables |
| `git diff --check` | PASS |
| Reviewer độc lập, read-only | Code/test không Critical/Important; lỗi evidence13 cũ đã sửa và reviewer kiểm lại, không còn Critical/Important; probe TLS được bổ sung theo Minor |

CI/PR mới: đang chuẩn bị; không suy PASS từ lịch sử. CI toàn workflow mới bắt
buộc xanh trước merge; không chạy lại JI-00→JI-50 local để thay CI.

## Hosted và rollback

Image pair hiện đang chạy (bản trước C; **không dùng làm rollback sau0029**):

- API: `sha256:231702c745ff902fca78937dfd5f56c3df39c70dd94794e0aa64782b9dd640e5`.
- Web: `sha256:f5ceb5da47ace0117e64a6e051a37c338b749b20dd922e2e31b6fa67a783f680`.
- Cả bốn service sourceSHA `d6280561a12cf50069ded12422734afb8c5e7335`.
- Runtime có OpenAI/Voyage/model/accounting, model `gpt-6-luna`, budget20USD/ngày.
  Proactive/Maps workers hiện đã bật từ bản cũ; phiên này chưa sửa cờ, budget hay quota.
  Năm safety-switch **defaults source** vẫn false; runtime CAPTCHA/cookie HTTPS
  là cấu hình đã có, không tắt bảo vệ auth để làm khớp default.

C/F PR, publication, rehearsal, migration, maintenance và rollback: chưa thực hiện.
Không có C digest rollback đã kiểm chứng. Backup được chủ dự án miễn, không báo
backup/restore đã đạt. Không được chạy F trên0028: ORM đọc cột provenance0029.

| Ca web thật trong prompt | Kết quả phiên này |
| --- | --- |
| 1: image/schema/service/health | Metadata bản cũ/schema0028/4healthy/0restart/live-ready200; chưa đạt release F/schema0029 |
| 2: desktop/mobile/auth/guest/nav | Chưa chạy browser phiên này; không dùng smoke lịch sử làm PASS |
| 3–5: retrieval/edit/delete/settings | Chưa chạy; chưa có release F và credential migration |
| 6–8: skills/auto-memory/orchestration/group/proactive | Chưa chạy; release/QA và kiểm soát trần chi phí còn thiếu |
| 9: recovery/Maps regression | Chưa chạy hosted; không gọi Apify/Google |
| 10: usage/cleanup | Không tạo QA/provider call/job mới; không có dữ liệu QA cần xóa |

Bước tiếp theo: cấp owner credential bằng file runtime ngoài repo có ACL hạn chế
hoặc kênh hiện hữu tương đương; chỉ thông báo đường dẫn, không gửi secret vào chat.
Sau đó xác minh target/TLS/identity kín, tiếp tục C/rehearsal0029/F theo pipeline;
paid smoke chỉ chạy khi có cơ chế chặn tổng chi phí1USD đã kiểm chứng.
