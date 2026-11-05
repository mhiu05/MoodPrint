# 13 — Bằng chứng thực thi release JI-51

Phiên bắt đầu ngày 05/11/2026, múi giờ Asia/Bangkok. Ủy quyền: prompt release
được chủ dự án gửi trong chat; trần chi phí phát sinh 1 USD. Không suy quyền từ
prompt cũ hoặc tài liệu lịch sử. Không đọc `E:\MoodPrint\backend\.env`.

## Trạng thái hiện tại

**Tiếp tục 05/11 08:51 UTC+7:** chủ dự án cấp credential qua `backend/runtime.txt`.
Đã đọc duy nhất file được chỉ định vào bộ nhớ, chọn hai key cần thiết và đặt bản
runtime tạm trong thư mục ngoài repo có ACL hạn chế. Không đọc `.env`, không stage
`runtime.txt`. Kiểm target/TLS/identity chỉ đọc PASS; revision vẫn0028. Blocker
credential bên dưới là checkpoint lịch sử, đã được gỡ. Chưa có hosted mutation.

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

### Thiết kế/thứ tự triển khai C — bổ sung thực thi

Dùng skill writing-plans/executing-plans cho phần source chuyển tiếp của runbook.
Không cần phát minh thiết kế sản phẩm mới hoặc hỏi lại các bước release đã được duyệt.

- [x] Xác minh credential target/owner/TLS/revision kín.
- [ ] Hoàn tất PR39 CI xanh, merge không gỡ hold; pin F gồm sửa an toàn.
- [ ] Tạo C từ manifest **210 path** thuộc diff F so với baseline0028, phục hồi
  có chọn lọc app/tests/contracts/docs cần khớp source; bảo toàn reviewed SQL,
  ledger, workflow và mọi thay đổi main ngoài phạm vi.
- [ ] RED readiness0029 trên ORM0028; GREEN readiness0028/0029; giữ từ chối revision khác.
- [ ] C online migration head0028 khớp ORM0028. Giữ nguyên byte migration0029 tại
  `deploy/supabase/reviewed-migrations/` chỉ phục vụ exporter offline; exporter
  mở thêm đúng directory cố định đó **chỉ** cho range0028→0029. Không đưa0029 vào
  online version_locations, không sửa SQL/hash và không cho caller chọn SQL tùy ý.
- [ ] Targeted regression/static/docs/SQL checks, reviewer độc lập, PR C đầy đủCI.
- [ ] Chỉ gỡ hold khi sẵn sàng vận hành; exact-main CI/publish/attestation/deployC.
- [ ] Rehearsal schema snapshot chỉ cấu trúc + dữ liệu synthetic trên disposable;
  không sao chép dữ liệu người dùng sau khi chủ dự án bỏ backup. Báo rõ giới hạn:
  đây không chứng minh restore bản sao dữ liệu production.
- [ ] Maintenance/fence worker/poller → approvedSQL0029 → verify → PR Frestore
  snapshot + sửa an toàn → exact-main CI/publish/deploy → smoke/khôi phục traffic.

Ruling C: tách nguồn offline review khỏi online migration chain giúp C thực sự
giữ ORM/head0028, đồng thời CI vẫn so sánh nguyên văn approved0029. Giữ0029 trong
online chain rồi bỏ qua drift sẽ làm sai cổng `alembic check`, nên không làm vậy.
F khôi phục file0029 về directory gốc và exporter gốc, giữ `_env_file=None`.

### Kết quả C local / rehearsal — 05/11 08:54–09:07 UTC+7

- Readiness RED chính thức:1failed/2passed/30deselected/9,20s;0029 trả503 trước
  mở window. Một lượt trước đó có ImportError ở test metadata (sửa import đúng
  module, không coi lỗi setup là bằng chứng RED). GREEN:3passed/7,86s.
- Offline export khi C chưa có directory review:1failed/29deselected/27,03s.
  Sau thêm config cố định:30artifact tests passed/31,38s.
- Config review-only online guard: RED1failed/2,28s, engine stub chặn mọi network;
  GREEN1passed/1,73s, từ chối trước engine. Không mở remote Alembic guard.
- Regression backend C:114passed/0failed/0skipped/90,47s, runner93,734s
  (`test_foundation`, `test_readiness`, `test_guest_cleanup_recovery`,
  `test_reviewed_artifacts`, `test_database_operations`).
- Ruff PASS; mypy184files PASS; frontend typecheck PASS,241unit +2script checks
  PASS,build PASS/5,18s. OpenAPI/contracts xuất lại và khớp baseline0028.
- Docs PASS:182Markdown/1161links/141operations/113settings/61tables;
  SQLchecker12pinned/12consumed PASS. Không thay lock/dependency/workflow.
- Snapshot cấu trúc226072bytes,sha256
  `41d375cb1e03f9c6d9f208252ad3cb328072b8ded62be97ff62f782f690557f1`;
  revision metadata1351bytes,sha256
  `cab0d8afbea8589ae7368fc785b51a1e7eedb8b307221e64977ddb8bf6d0d59a`.
  Không dump dữ liệu ứng dụng; artifacts ở thư mục ngoài repo ACL hạn chế.
- Restore vào owned scratch `_test`, `alembic check` C trên cấu trúc0028 PASS.
  Seed4hàng synthetic(user/entry/proposal/memory), tổng5hàng gồm revision.
  Rollback transaction0029 PASS; sau đó exactSQL0029commit và8checksPASS
  (revision,NoSchemaCreate,row-count,RLS,policies,DML,API-role-denial,Auth-structure).
  Legacy approved-memory origin/default và entry synthetic giữ nguyên.
  C ASGI ready200 trên0028 và0029. Scratch đã hủy có ownershipcheck;
  các role local do rehearsal tạo đã drop. Không restore dữ liệu người dùng.
- Reviewer độc lập so403filebaseline: source app/frontend/migration online chỉ
  khác readiness có chủ đích; kiểm207/210manifestpath (3envexamples không đọc).
  Không Critical/Important; migration source0029byte-identical SHA256
  `52661ecabf74ff271ea4ef297a58cd89aba7dd8158b01723b17baa7bf19eb748`.
- Gỡ hold trong ứng viên PR C theo ủy quyền release; main vẫn held cho tới mergeC.
  Chưa publish/deploy C và chưa migration hosted; CI mới vẫn bắt buộc.
- Browser QA riêng đã mở; chủ dự án gặp lỗi tải CAPTCHA trước đăng nhập.
  Đang chẩn đoán, không bypass và chưa đọc dữ liệu tài khoản.

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

## Git và CI của bản sửa preflight

- Commit code/test: `2d8f233073e0eb6cd457e4a4a5b2a1ee1d2f56d0`.
- Đã push `release/ji51-preflight`, mở [PR39](https://github.com/mhiu05/MoodPrint/pull/39).
- Tại checkpoint 05/11 08:45 UTC+7, [CI push](https://github.com/mhiu05/MoodPrint/actions/runs/41950420709)
  và [CI PR](https://github.com/mhiu05/MoodPrint/actions/runs/41950430245) đang chạy
  bước backend, chưa có conclusion. Không gọi CI xanh hoặc merge hoàn tất.
- Commit cập nhật bằng chứng sau commit code vẫn thuộc PR39; trạng thái exact-head
  mới nhất tra tại [PR39 checks](https://github.com/mhiu05/MoodPrint/pull/39/checks).
- Chưa merge PR39; chưa thay main, chưa publish C/F. Publication hold nguyên vẹn.
- Disposable container do phiên tạo đã được hủy bằng `disposable_postgres.py --remove`
  có kiểm ownership, exit0; credential disposable đã xóa. Không đụng container khác.

CI toàn workflow mới bắt buộc xanh trước merge; không chạy lại JI-00→JI-50 local
để thay CI. Bản ghi này là checkpoint tại blocker credential, không phải báo cáo
release thành công. Không lấy CI lịch sử thay kết quả mới.

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
