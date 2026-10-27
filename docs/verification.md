# Kết quả kiểm chứng ngày 28/10/2026

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
