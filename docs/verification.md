# Kết quả kiểm chứng

## Journal intelligence — 04/11/2026 (đang triển khai)

Nguồn số liệu đầy đủ, RED/GREEN và giới hạn nằm trong
[execution ledger](implementation-plans/journal-intelligence-and-matching-removal/08-execution-ledger.md).
Các kết quả dưới đây là local/synthetic, chưa xác minh bản tính năng trên hosted.

| Phạm vi | Kết quả đã quan sát |
| --- | --- |
| Backend baseline `e2c3e5e8` | 1964 passed, 3 skipped, 4732,76 s |
| JI-01 RED (đổi defaults, chưa ghim nền) | 307 failed, 1661 passed, 3 skipped, 4485,46 s; danh sách từng failure trong ledger |
| JI-01 GREEN snapshot | 1968 passed, 3 skipped, 4732,79 s |
| Checkpoint A backend sau sửa | 2065 passed, 3 skipped, 0 failed; 2233,27 s; cả 2068 test đã thu thập |
| Checkpoint B backend (có JI-40) | 2082 passed, 3 skipped, 0 failed; 2715,39 s; cả 2085 test đã thu thập |
| Frontend sau gỡ social và thêm công tắc | Typecheck pass; 204 unit tests + 2 script checks; build pass, RealApp 311,30 kB/gzip 97,17 kB |
| Fixture browser | Baseline 445 passed/15,0 phút; A serial 382 passed/14,3 phút; B serial 384 passed/15,4 phút; final 385 passed/13,9 phút (runner836,625s); các lượt chẩn đoán/bị ngắt ghi trong ledger |
| Fullstack | A 38 passed/6,2 phút; B retry 38 passed/7,2 phút; final 38 passed/6,4 phút (runner403,469s), timeout giữ nguyên; fake document/query embeddings và synthetic SDK model |
| JI-40 | 32 backend targeted + 204 regression pass; typecheck/205 unit tests + 2 script checks/build pass; 7 browser skill tests pass |
| JI-30 + JI-31 | Commit nguyên khối `61469170`; 269 và 228 regression pass; 68 precommit pass; 206 frontend unit tests/37 files + 2 script checks/typecheck/build pass; 3 browser memory tests pass |
| JI-25 | `43d27e4c`; 51 orchestration/retrieval regression tests pass, gồm query ngoài owner lock và fallback khi settings/dimensions đổi hoặc timeout |
| Review cuối | 0 Critical, 2 Important tái hiện RED rồi sửa; nhóm hậu review 61 pass; 1 Minor capability view cũ khi đổi bot được ghi deferred, backend giữ 422 |
| Migration local | Upgrade 0029 + Alembic check không drift; tests migration 10 passed; cụm migration/memory/readiness 79 passed/446,06 s |
| Retrieval | 105 regression tests pass; 17 targeted retrieval/eval tests pass sau bổ sung marker/fallback |
| Fake eval | 40 entry/15 query, 55 fake calls; recall@6 paraphrase 0→1,0, keyword giữ 1,0; không chứng minh chất lượng Voyage |
| Linux deployment unit tests | Image test có sẵn, repo mount read-only, network none, Docker socket chỉ cho synthetic Compose/Caddy: 37 tests OK/11,479 s ở lượt final sau khôi phục Docker |
| Backend final local | Đủ2131nodes:2128pass/3skip baseline,0missing/duplicate/unknown/nonzero;188reports cùng fingerprint (187Windows+inboxLinux),sum3461,421s; không phải một lượt nguyên khối. CI nguyên khối giữ nguyên,bắt buộc xanh trước merge |
| Timing inbox | Windows50,6/69,0ms fail; baseline cũng74,9ms fail. Nguyên file Linux10pass/17,08s,ngưỡng50ms giữ nguyên; không gọi Windows SLO đã đạt |
| Web công khai hiện hữu | Homepage và health/live200; trang login có email/password, không tràn ngang ở1440/390px. Chỉ GET/HEAD cùng domain; CAPTCHA ngoài domain bị chặn, chưa login hoặc kiểm chứng tính năng mới |
| Tích hợp source | Marker release hold có sẵn được dùng lại để merge source mà không tự publish/deploy; rollout C→0029→F vẫn là công việc riêng cần chủ dự án duyệt |
| Chưa chạy | Provider thật, live eval có phí, rehearsal snapshot hosted và hosted schema/deploy |

Không đọc dữ liệu hosted hoặc gọi provider thật. Có sự cố offline Alembic subprocess
có thể đọc dotenv trái giới hạn trong lượt regression đầu; đã thông báo, ghi ledger
và sửa cả exporter lẫn Alembic để luôn tắt dotenv, có test chặn truy cập thực sự.
Không có secret được in ra hoặc kết nối hosted từ đường xuất SQL offline đó.
Một lượt container test sau đó để traceback in credential **disposable local**;
artifact đã che và container/credential cũ đã hủy, thay bằng disposable mới.
Không phải credential hosted/provider; chi tiết và kết quả lỗi giữ trong ledger.

## Baseline tài liệu ngày 28/10/2026

Kết quả bên dưới là baseline của đợt tài liệu trước. Phần triển khai guest/feedback/tour có [execution ledger riêng](guest-experience/implementation/evidence/execution.md) và [release gates PARTIAL](guest-experience/implementation/evidence/release-readiness.md); không dùng baseline này để suy ra guest đã được phép mở public.

Trang này ghi bằng chứng đã thực thi của đợt cập nhật tài liệu. **Trạng thái kiểm tra local: PASS.** Không dùng mô tả CI để thay kết quả chạy thực tế.

## Phạm vi

Tài liệu kiến trúc và năm subsystem, các liên kết hướng dẫn cũ, cùng sáu file frontend đã sửa trước phiên làm việc. Người dùng đã xác nhận commit cả việc xóa `.env.example` ở gốc phát sinh trong phiên; giữ nguyên các template backend. Không sửa `.gitignore`, cấu hình bí mật, schema ứng dụng hoặc provider implementation. Browser tests được đồng bộ với điều hướng tìm bạn và accessible label micro hiện tại; giữ kiểm tra consent, microphone permission và transcript không tự gửi.

## Môi trường

Windows/PowerShell, Python 3.12.13, uv 0.11.14, Node.js 24.13.0, npm 11.6.2; dependencies hiện có từ lockfiles. CI cấu hình Node 22, do đó kết quả local không thay thế matrix runtime của CI. PostgreSQL/pgvector `0.8.2-pg17` trong container disposable bind `127.0.0.1:15432`, database riêng cho pytest/migration/fullstack. Browser fixture server 5190, fullstack 8002/5174; synthetic accounts và SDK fake model, không dùng hosted data hoặc live model.

## Kết quả

| Scope | Lệnh đã chạy | Kết quả quan sát |
| --- | --- | --- |
| Backend lint | Từ backend: `uv run --locked ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/provision_supabase_runtime.py ../scripts/check_reviewed_artifacts.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py ../scripts/check_docs.py` | PASS, All checks passed |
| Backend types | `uv run --locked mypy app` | PASS, 89 source files |
| Backend unit/API/PostgreSQL | `TEST_DATABASE_URL` trỏ DB local `moodprint_docs_test`, `uv run --locked pytest -q` | PASS, **642 passed**, không có integration skip, 521,83 giây |
| Alembic chain | DB rỗng `moodprint_migration_test`, `uv run --locked alembic upgrade head`, `alembic current`, `alembic check` | PASS, `0015_context_privacy (head)`, No new upgrade operations detected |
| Contract export/generate | `uv run --locked python ../scripts/export_openapi.py`; từ frontend `npm.cmd run contracts:generate`; root `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` | PASS, không drift |
| Frontend types/unit | `npm.cmd run typecheck`, `npm.cmd test` | PASS, **13 files / 73 tests** |
| Frontend build | `npm.cmd run build` | PASS; warning main chunk 528,02 kB sau minify, gzip 169,55 kB |
| Browser fixture E2E cuối | `npx.cmd playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP\moodprint-docs-e2e-verified"` | PASS, **187 passed**, 4,8 phút; server riêng 5190, gồm hai regression mới |
| Synthetic fullstack | Từ backend với DB `moodprint_fullstack_test`: `uv run --locked python ../scripts/test_fullstack.py --reporter=list --output "$env:TEMP\moodprint-docs-fullstack"` | PASS, **28 passed**, 7,2 phút; scorer mặc định v1 |
| Fullstack matching v2 | DB disposable mới `moodprint_matching_test`, `E2E_MATCHING_SCORER=v2`; `uv run --locked python ../scripts/test_fullstack.py matching-v2.spec.ts --reporter=list --output "$env:TEMP\moodprint-docs-fullstack-v2"` | PASS, **2 passed**, 7,7 giây; server/browser cùng chọn v2 |
| Reviewed SQL integrity | Root: `uv run --project backend --locked python scripts/check_reviewed_artifacts.py` | PASS, 9 pinned approvals, 9 consumed |
| Linux deployment unit tests | `docker run --rm --network none --mount 'type=bind,source=E:\MoodPrint,target=/repo,readonly' --workdir /repo --env PYTHONDONTWRITEBYTECODE=1 python:3.12-slim python -m unittest discover -s deploy/aws/tests -v` | PASS, **14 tests**, Linux container offline |
| Workflow syntax | `docker run --rm --network none --mount 'type=bind,source=E:\MoodPrint,target=/repo,readonly' --workdir /repo rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667` | PASS, exit 0, không diagnostics |
| Documentation inventory | `uv run --project backend --locked python scripts/check_docs.py` | PASS, **32 Markdown files, 208 local links, 100 operations, 48 settings, 38 tables**; kiểm tra path và inventory coverage, không gọi network |
| Patch whitespace | `git diff --check` | PASS, không lỗi whitespace |

Hai regression tests mới cho gender selector và starter visibility đã được chạy riêng (`--grep 'AI starters edit|gender selector'`) đạt **2/2**, rồi nằm trong toàn bộ browser suite cuối đạt **187/187**. Đã xem ảnh tổng hợp ở phone 390px và desktop 1440px bên cạnh geometry/axe/keyboard checks tự động.

## Baseline failures và cách xử lý

- Browser baseline trước sửa test: **178 passed / 7 failed**. Ba ca discovery còn yêu cầu bridge/nudge đã bị thay đổi frontend có sẵn loại bỏ; bốn ca voice còn tìm accessible name cũ. Đã thay bằng kiểm tra navigation đến đúng profile/suggestions, teen không fetch candidate, và nút micro tên hiện tại; giữ assertions permission denial, no premature upload và transcript không tự gửi.
- PostgreSQL Compose ở 55432 không bind được trên Windows. Chuyển sang container disposable riêng ở 15432; không đổi Compose hoặc dừng process người dùng.
- Deployment unit tests chạy trực tiếp Windows bị `ModuleNotFoundError: fcntl`. Chạy lại đúng môi trường Linux trong container offline: 14/14 đạt; không mock bỏ kiểm tra.
- Có một lệnh Ruff từ root dùng nhầm paths `app tests` trả E902; đã chạy lại đầy đủ từ `backend/` cùng script checker mới và đạt. Không tính lệnh sai thư mục là lint pass.
- Lượt mở rộng đầu có **186 passed / 1 failed**: regression starter mới thất bại vì test fixture trả transcript rỗng khi UI reconcile sau completed. Đã sửa response GET của fixture để giữ message đã accepted; không sửa production state/reconciliation để làm test đạt. Sau sửa fixture, targeted tests 2/2 và final browser suite 187/187 đạt.

## Matching benchmark

Đã chạy `uv run --locked python -m evals.matching.benchmark --out <report-trong-TEMP>` hai lần, không sửa fixture/weights/threshold:

| Điều kiện | V2 p95 tại 600 personas | Gate |
| --- | --- | --- |
| Cùng lúc browser suites/build còn hoạt động | 153,211 ms | Không đạt `<50 ms`; các criteria khác đạt |
| Chạy riêng sau khi các suite/build kết thúc | 45,209 ms | Đạt toàn bộ metric gates trên proxy labels |

Chất lượng cố định giữa hai lần: NDCG@5 v2 0,8728, coverage 1,0, Gini 0,2248, reason faithfulness 1,0, symmetry violations 0. Timing nhạy với CPU contention; report không phải production load evidence. Labels vẫn provisional/rule-based; giữ mặc định v1, không bật v2 production từ kết quả này.

## Review và phạm vi chưa kiểm chứng

Đã review độc lập theo code-review skill và đối chiếu lại các findings với nguồn: sửa Unicode prose của hai bảng inventory, cookie max-age so với server idle expiry, effective saved-chat retention 30 ngày, helper EXECUTE so với raw Auth grants, operation AI `/messages`, và temporary context so với persistent backup. Không thay đổi security implementation để làm khớp tài liệu.

Không chạy live OpenAI/Voyage, hosted Auth/migration, AWS deployment, email delivery, backup restore, paid eval/judge hoặc human matching study. Không chạy lại toàn bộ Docker image/proxy/load/dependency-audit jobs của CI trong lượt tài liệu này. Đây là các giới hạn bằng chứng, không phải kết quả PASS production. CI remote sẽ có kết quả riêng sau push.

Artifacts browser/benchmark nằm trong TEMP và các screenshot do existing specs tự ghi được chuyển khỏi repository; không commit chúng. Không đổi `.gitignore`.

## Bàn giao Git

Base trước phiên: `aef1edc`. Các commit tách theo architecture/local guide, agents, frontend docs, backend docs, Supabase, matching, xóa root environment example theo xác nhận người dùng, docs checker/CI, chat/voice, identity và bằng chứng kiểm thử cuối. Dùng `git log --oneline aef1edc..main` để xem từng subject/body. Push và remote SHA được xác minh sau commit bằng chứng và báo trong bàn giao cuối; không diễn giải local PASS thành remote CI đã hoàn tất.
