# 13 — Bằng chứng thực thi release JI-51

Phiên bắt đầu ngày 05/11/2026, múi giờ Asia/Bangkok. Ủy quyền: prompt release
được chủ dự án gửi trong chat; trần chi phí phát sinh 1 USD. Không suy quyền từ
prompt cũ hoặc tài liệu lịch sử. Không đọc `E:\MoodPrint\backend\.env`.

## Trạng thái hiện tại

### Kết quả release — 05/11/2026 11:29 UTC+7

**Đã release F lên public URL.** Main và cả bốn service chạy
`0573af5b50c0584c523e5119755479fcf47fae74`, schema `0029_journal_intelligence`.
Semantic/auto-memory journal **tắt**; paid smoke/backfill được chủ dự án hoãn để
giữ trần phiên 1 USD. Không gọi đây là nghiệm thu đầy đủ AI/hybrid.

- API: `sha256:e893d44b8e379681849d6682145c02ee44868550aad934587e8c60d571a1ccfb`.
- Web: `sha256:7e0e5d591398e208949a152fcbd062f1187e48ef7c414606cff1cad2d69d40d0`.
- [PR40 C](https://github.com/mhiu05/MoodPrint/pull/40),
  [Verify C main](https://github.com/mhiu05/MoodPrint/actions/runs/41956696184),
  [publish C](https://github.com/mhiu05/MoodPrint/actions/runs/41960425282): success.
- [PR41 F](https://github.com/mhiu05/MoodPrint/pull/41),
  [Verify F exact-main](https://github.com/mhiu05/MoodPrint/actions/runs/41963189843),
  [publish F](https://github.com/mhiu05/MoodPrint/actions/runs/41966776352): success.
  Manifest/API/web attestations được kiểm độc lập; poller kiểm lại trước deploy.
- F exact-main CI: **2131 backend pass/4 skip**, 1110,97 s;
  **206 frontend unit + 2 script checks**, **386 browser**, **38 fullstack**;
  Linux deploy **37 pass**. Đây là kết quả phiên release, không lấy CI PR38 thay thế.
- Maintenance 1: **10:39:09–10:43:45**, 4 phút 36 giây, migration rồi tạm mở C.
  Maintenance 2: **11:20:50–11:29:25**, 8 phút 35 giây, chuyển F và smoke miễn phí.
  Tổng hai cửa sổ: **13 phút 11 giây**. Gate cuối **OFF**;
  timer **active/waiting/enabled**, pollservice thành công/exit0.
- Bốn service healthy, restart0, không có `feature_degraded flag=ai_enabled`;
  homepage/live/ready200 qua public URL **không header gate** sau mở traffic.
- Backup dữ liệu **được chủ dự án miễn**, không có bản backup dữ liệu mới.
  Rehearsal chỉ schema hosted + dữ liệu synthetic: restore, exact SQL0029,
  transaction rollback, 8 invariant checks và C readiness0029 PASS.
  Hosted migration committed 10:40:19, 8 checks PASS; 973 hàng/62 bảng hiện có
  được bảo toàn tại apply. Không replay migration, không downgrade.
- C rollback pair đã kéo/chạy thật trên0028 và0029 (digest ở checkpoint dưới).
  **Chưa thực hiện F→C rollback**; chỉ chuẩn bị và xác minh C làm target hợp lệ.

### Bảng kiểm web thật trên F — 11:23–11:30 UTC+7

| Ca | Kết quả phiên release |
| --- | --- |
| 1. Image/schema/health/queue | **PASS** đúng F/pair/schema0029; 4 healthy/0 restart; live/ready200; journal queue, embedding, auto-memory đều0 |
| 2. Auth/layout/nav/guest | **PASS phần đã chạy**: chủ dự án login trực tiếp QA adult/consent; session hợp lệ; logout về login. 1440px/390px trên Trợ lý/Nhật ký/Tài khoản không overflow; `/connect`→`/assistants`. Guest intro mở được; **chưa submit guest signup/chưa nghiệm thu full guest flow** |
| 3. Ba entry/retrieval | **PASS tạo 3 entry synthetic**; **chưa chạy indexing/query synonym/citation/hybrid**, paid phase hoãn |
| 4. Edit/delete | **PASS CRUD**: PUT200/version tăng, sửa giữ sau reload; cancel delete giữ entry; DELETE200 đúng3entry QA, GET từng ID đã xóa404. **Chưa kiểm invalidation/citation qua provider** vì indexing tắt |
| 5. Settings | **PASS** notice, opt-out rồi khôi phục setting QA; available=false cả semantic/auto-memory, indexed/pending0. **Chưa kiểm keyword fallback bằng câu trả lời AI hoặc backfill thật** |
| 6. Bốn skill | **Chưa chạy hosted paid execution**, giữ nguyên backend422/quyền; CI fake-provider xanh không thay hosted smoke |
| 7. Auto-memory | **Chưa chạy**, runtime tắt theo quyết định chi phí; không giả lập thời gian/job production |
| 8. Consult/hoạt động/group/proactive | **Chưa chạy hosted**, không ép job hoặc gửi provider call |
| 9. Recovery/Maps | **PASS journal offline**: browser offline, lỗi hiển thị, draft còn nguyên, online retry tạo201; chỉ3entry do phiên tạo. AI retry/cancel/recovery **chưa chạy**; Maps fixture nằm trong386browser CI, không gọi Google/Apify thật |
| 10. Usage/cleanup | **PASS phần miễn phí**: 0 lần gửi AI/voice từ QA, 3/3entry đã xóa, settings khôi phục, logout; indexed/pending/auto-memory0. Không để job journal mới |

Không có uncaught JavaScript page error trong lượt QA đăng nhập F. Console có
HTTP lỗi có chủ đích (offline,404 sau delete,401 khi logout), một502 khi container
đang chuyển và cảnh báo/lỗi challenge Cloudflare trên trang login/guest; không
báo toàn bộ console sạch hoặc gọi CAPTCHA tự động đã đạt. Không bypass CAPTCHA.

Harness ban đầu nhầm composer giữ entry vừa lưu là form tạo mới: lần thứ hai
thực tế PUT entry QA đầu, không phải POST. Đã kiểm GET đúng ID do phiên tạo,
ghi lại version2, bấm “Viết khoảnh khắc mới” để tạo thêm hai entry, rồi tiếp tục.
Không có duplicate do retry mất mạng; chỉ đúng3ID trong manifest QA được xóa.
Một strict locator `nav` cũng được thu hẹp thành navigation “Điều hướng chính”.
Đây là sửa harness kiểm thử, không phải sửa nóng source/container.

### Chi phí và giới hạn nghiệm thu

Không khởi tạo paid provider request từ QA; chi phí provider **do ca QA chủ động
gọi: 0 USD**. Hai cờ journal mới false trước F startup; queue/embedding/auto-memory0
trước và sau QA. Không tăng model, budget hoặc quota. Snapshot accounting sau mở
traffic: liability bảo thủ **10,630033550 USD**, ceiling20USD, còn **9,369966450 USD**.
Liability có reservation, **không phải hóa đơn thực tế**, không gán hoạt động nền
đã có của toàn site cho ca QA. Không tuyên bố tổng hóa đơn toàn site bằng0.

Khả năng semantic/hybrid, auto-memory và paid skill/chat vẫn **chưa kiểm chứng
hosted** theo lựa chọn giữ1USD. Minor đã defer của phiên trước (menu skill khi
đổi bot) chưa được sửa trong release này; backend validation không nới.

Các checkpoint dưới đây là **lịch sử**, không thay kết quả cuối ở trên.

### Theo dõi sau mở traffic và bàn giao tài liệu

Từ11:29:25 đến11:34:15 UTC+7 (4phút50giây), kiểm lại qua SSM metadata và
public HTTP: vẫn đúng F/pair, bốn service healthy/restart0, gateOFF,
timeractive/waiting/enabled, pollservice exit0. Journal queue/embedding/auto-memory0;
accounting liability không tăng so với snapshot trước QA. Đếm log có giới hạn từ
lúc mở traffic: API/proactive/Maps đều0traceback và0dòng mứcERROR; không in log.
Đây là cửa sổ quan sát hữu hạn, không thay monitoring dài hạn.

Đã gỡ route/header gate khỏi browser QA, logout và trở về homepage public200.
Hai container DB disposable của phiên đã hủy bằng kiểm ownership. Automatic
approval review chặn xóa ba file credential/header/runtime-JS tạm ở thư mục ops
ngoài repo với lý do “blocked by policy”; không thử vượt chặn. Các bản tạm vẫn
được ACL hạn chế; không commit. File `backend/runtime.txt` do chủ dự án tạo giữ
nguyên/untracked. Không đọc/sửa `backend/.env`, không sửa `.gitignore` hay stash.

Ledger08/evidence13 được commit/push qua nhánh `docs/ji51-release-evidence` và PR
riêng. Chủ ý chưa merge PR tài liệu để giữ main đúng0573 đã được exact-main
CI/publish xác minh; mọi merge tài liệu sau này phải xét lại pipeline exact-main.
Docs checker182Markdown/1165links PASS, diffcheck PASS, SQL vẫn7488byte/hash đã
duyệt; scanner phần thêm không thấy credential/account/instanceID. Review độc
lập tài liệu chỉ ra một lỗi spacing CLI, đã sửa. Không commit browser artifacts.

### Checkpoint 05/11 10:43 UTC+7

**Đã release C và migrate0029; F chưa chạy.** C main
`a457fde6bd89815f995d9f836fa7a1bff0f52740` đang là image pair đã xác minh
attestation. F main `0573af5b50c0584c523e5119755479fcf47fae74` đã merge;
Verify exact-main đang chạy, chưa publish/deploy F tại checkpoint này.

- C API: `sha256:850070ae755459b1c6628daf7d2b882f2a5948e60a0e2b11c376c973254f956b`.
- C web: `sha256:fc563c43633835fe335a0bf173c5bc56a795f661d250f3a7f43fe7478fc9175f`.
- SQL0029 transaction committed,8checksPASS,973hàng hiện có trong62bảng giữ
  nguyên. Kiểm revision độc lập qua TLS xác nhận0029. C ready200 sau migration.
- Chủ dự án chọn **giữ trần1USD, hoãn paid smoke/backfill**. Runtime SSM25→26
  chỉ thêm `JOURNAL_SEMANTIC_ENABLED=false`, `JOURNAL_AUTO_MEMORY_ENABLED=false`;
  mọi key khác, model và budget20USD/ngày giữ nguyên. Hai cờ đã có trong C thực tế.
  Các paid default cũ STT/GUEST_SEMANTIC/SEMANTIC_MEMORY vốn false đã được xác minh.
- Maintenance bắt đầu10:39:09UTC+7; fence timer trước khi chờ pollservice idle,
  gate enabled rồi dừng API/proactive/Maps. API C đã khởi động lại/ready200.
  Đang tạm mở traffic trên C/schema0029 trong lúc chờ F exact-mainCI;
  poller tiếp tục dừng để không tự chuyển F trước smoke/gates.
- Phiên Playwright QA riêng đã được chủ dự án đăng nhập; session200,
  registered/adult/eligible true, consentAI/MEM true. Không in ID/alias/token.
  Header gate chỉ thêm cho originMoodPrint; POST gửiAI/group/voice bị chặn
  trong riêng browsercontextQA. Không gọi provider trong các ca QA phiên này.

Các mục preflight “chưa release/thiếu credential” sau đây là **checkpoint lịch sử**.

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

### Release C →0029 →F — kết quả tiếp tục

| Bước | Kết quả thực tế |
| --- | --- |
| PR40 | Merged09:40:06UTC+7, mainC `a457fde6bd89815f995d9f836fa7a1bff0f52740` |
| C push/PR CI | [41953385033](https://github.com/mhiu05/MoodPrint/actions/runs/41953385033),[41953466317](https://github.com/mhiu05/MoodPrint/actions/runs/41953466317) success; push summary1980backendpass/4skip,241frontendunit+2script,445browserpass,50fullstackpass |
| Exact-main C Verify | [41956696184](https://github.com/mhiu05/MoodPrint/actions/runs/41956696184) completed/success, eventpush/main/exactSHA |
| C publication | [41960425282](https://github.com/mhiu05/MoodPrint/actions/runs/41960425282) success; [releaseC](https://github.com/mhiu05/MoodPrint/releases/tag/staging-a457fde6bd89815f995d9f836fa7a1bff0f52740) |
| C provenance | ManifestSHA256 `adf02ad2eda80d93795fae02a58f6beb63b6f31adcbb52c7544fc5dd2771d5d9`; manifest/API/web `gh attestation verify` source-digest/main-ref/workflow identity/self-hosted denial tất cảPASS |
| C deployed | SSM xác minh actual pair/source đúngC,4healthy/0restart,live/ready200/schema0028 trước migration; installed deploy/poller/compose/Caddy khớp sourceLF |
| Gate attempt đầu | Chưa mutation: preflight từ chối “Poller still running” đúng tick5phút. Sau ngắt phiên kiểm gateOFF/serviceshealthy/schema0028; sửa thao tác fence timer trước waitidle, không bypass poller lock |
| Maintenance/migration |10:39:09UTC+7 gateON/timerSTOP/writersSTOP; apply10:39:45→10:40:19, đúng7488bytes/hashSQL0029; committed/PASS8checks; không replay |
| Verify sau migration | Independent read-onlyTLS revision0029; restartAPI C,ready200; workers giữ dừng đến khi tạm mở C trong lúc chờCI |
| PR41 | [PR41](https://github.com/mhiu05/MoodPrint/pull/41) merged10:41:44UTC+7,mainF `0573af5b50c0584c523e5119755479fcf47fae74`; source backend/frontend/scripts/workflow bằngsafeF1c64affa |
| F branch CI | [PR41954843759](https://github.com/mhiu05/MoodPrint/actions/runs/41954843759),[push41954834299](https://github.com/mhiu05/MoodPrint/actions/runs/41954834299) success trênhead `a57d2f0245f0e3244cabd344af572c4f9b8ffa4f` |
| F exact-main CI | [41963189843](https://github.com/mhiu05/MoodPrint/actions/runs/41963189843) đang chạy tại10:43UTC+7; không suy từbranchCI |

Hosted apply dùng script repo đã sửa, args `--upgrade 0029 --approved-sha256 <hash>
--apply`; credential chỉ trong env của process từ file runtime riêng, `_env_file=None`.
`PGOPTIONS` giới hạn lock5s/statement60s. Report an toàn giữ ở thư mục ops ngoài
repo; không commit raw runtime/backup/browser log. Chủ dự án miễn backup; schema
snapshot+synthetic rehearsal không được gọi là data-backup restore proof.

### Tiếp tục C/F — 05/11 09:14–09:20 UTC+7

- PR39 CI exact-head `efa4ff4b` đã completed/success cả
  [push41950633391](https://github.com/mhiu05/MoodPrint/actions/runs/41950633391)
  và [PR41950641821](https://github.com/mhiu05/MoodPrint/actions/runs/41950641821).
  Merge bình thường (không admin bypass) lúc09:14:21, main
  `1c64affa98ad1a52630f0cf62874ded123eb91df`; hold vẫn còn ở commit này.
- Pin snapshot F an toàn bằng branch `release/ji51-feature-safe-snapshot` tại1c64affa.
- C đã commit/push `fe4cee6c3b711d04fbe29537344005fdebb0763a`,
  [PR40](https://github.com/mhiu05/MoodPrint/pull/40); fullCI
  [push41953385033](https://github.com/mhiu05/MoodPrint/actions/runs/41953385033)
  và [PR41953466317](https://github.com/mhiu05/MoodPrint/actions/runs/41953466317)
  đang chạy. Gỡ hold chỉ trong ứng viên C; chưa merge/publish/deployC.
- Một lần stage C dùng nhầm path `evals` ở root đã fail, commit không được tạo;
  branch push đầu chỉ mang head cũ efa4ff4b. Đã sửa stage có kiểm exit, commit
  thực tếfe4cee6c gồm đầy đủ restored-untracked source và reviewed-migrations;
  không tính lượt cũ làm CI của C.
- F ứng viên tạo trên Cfe4cee6c, phục hồi212path từ snapshot1c64affa, bỏ config
  review-only của C và đưa migration0029 về directory chuẩn. Staged diff so với
  snapshot an toàn có **0file backend/frontend/scripts/workflow/lock khác biệt**;
  chỉ khác gỡ hold và ledger/evidence. Docs/SQLchecker/diffcheck PASS.
- Reviewer F xác minh parity, không lỗi Critical/Important về source. F merge
  vẫn phụ thuộc C đang chạy, rollback digest, hosted0029 và gates vận hành.
- Cost gate: reviewer không tìm được trần tăng thêm1USD cho fullpaid smoke;
  reservation2USD/run là liability bảo thủ, không phải bill. Voyage journal chỉ
  có cap thao tác, thiếu aggregate-dollar cap. Hai cờ journal mới phải false
  trước Fstartup; không coi hai cờ này là fence các provider khác. Đã hỏi riêng
  chủ dự án về giữ1USD/hoãn paid phase hoặc cho phép10USD, chưa tự tăng trần.
- Chủ dự án xác nhận đã login QA trong Chrome thường. Agent-browser CAPTCHA
  trước đó có mã600010; script đã tải nhưng challenge thất bại. CLI mở Chrome
  với remote-debugging bị automatic approval review từ chối “blocked by policy”,
  không bypass. Chrome extension tạo tab được nhưng API điều hướng/evaluate/CDP
  có internal `timeoutMs` error; tab QA đã claim và markHandoff, chưa đọc nội dung
  tài khoản. Đây là blocker công cụ smoke, không phải bằng chứng lỗi app F.

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

## Hosted và rollback — checkpoint preflight lịch sử

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
