# MoodPrint — Audit testing và CI/CD

Snapshot **2026-11-02, Asia/Bangkok**, branch `test/11-2`, source HEAD `a3af3d4cef1c7de75b2ec2b65ea5743640fbb853`; working tree sạch khi bắt đầu. Phạm vi là audit, thiết kế, kế hoạch và evidence; không đổi workflow, tests, business logic, schema, `.gitignore` hoặc deployment trong phiên này.

## Kết luận

Suite có nhiều regression quan trọng và vẫn phản ánh cả chế độ năm companion lẫn rollout ba agent. **Chưa xác nhận test nào có thể xóa an toàn.** Vấn đề rõ nhất là kiến trúc CI tuần tự, phân loại database chưa đủ chính xác, helper phụ thuộc giữa test modules và khoảng cách giữa disposable verification với hosted compatibility.

Rủi ro P0 là project Supabase được source tham chiếu vẫn ở `0020_private_profile_retirement` lúc **15:25:42 ngày 02-11-2026 (UTC+7)**, thiếu `ai_runs.origin`, `ai_runs.parent_run_id`, `ai_proactive_jobs`. Source hiện chỉ chấp nhận `0024_three_agent_groups`. Đây là metadata đọc bằng transaction read-only qua connector; không chứng minh image đang phục vụ trên EC2 hay quyền của runtime role. Không migrate hoặc thử đăng nhập production trong audit. [Evidence](evidence/hosted-schema-readonly.json).

Readiness không bị thiếu: `backend/app/main.py` đã kiểm tra revision và Auth helper; Compose và `deploy.sh` gọi readiness. Khoảng trống là **kiểm tra candidate trước khi thay active deployment**, kiểm tra catalog/quyền thực tế ngoài version string và kiểm tra worker. `deploy.sh` chỉ xét health `api`, `web`; service `proactive` có healthcheck nhưng không nằm trong vòng chờ này.

## Số liệu có thể kiểm chứng

| Hạng mục | Kết quả |
|---|---|
| Inventory | 291 rows: 158 pytest files, 34 Vitest, 46 Playwright, 3 unittest, 1 Node test, 24 custom, 25 eval modules |
| Pytest collection tại HEAD | 1.715 cases; main CI cùng code tests: 1.711 pass, 4 skip |
| Vitest | 217 cases / 34 files; dynamic collection và local run cùng kết quả |
| Playwright required | 398 mocked UI / 23 files + 50 full-stack / 18 files |
| Optional tour | Thêm 5 cases với `MOODPRINT_TOUR_COMPATIBILITY=1`; không được required CI chạy |
| Release/Node tests | 19 unittest methods trong Linux CI; 1 Node regression chạy qua `npm test` |
| Taxonomy không an toàn để split ngay | 991 cases dùng fixture `database`; 154 cases trong 12 files chưa có marker `postgres` |
| Helper coupling | 87 `from tests.test_*` imports trong 47 Python files, gồm helper modules |
| Candidate review | 8 nhóm C01–C08; 0 confirmed deletion candidates, 0 duplicate Python bodies theo AST |
| Baseline | 8 successful jobs gần đây: median **1.419,5 s (23:39,5)**; range **1.130–1.762 s** |
| Main tham chiếu | Run `41298504384`: workflow 23:46, job 23:43; backend 9:31, frontend/browser 6:23, full-stack 5:15 |
| Trigger overlap | 8 cặp cùng source SHA/branch có push + PR trong mẫu 35 runs; 2 cặp cả hai thành công |
| HEAD mới nhất | Run `41410267512` FAIL: pytest 1.711 pass/4 skip, Vitest 217 pass, mocked UI 398 pass; full-stack 49 pass/1 fail |

PR checkout có thể là merge ref, nên cùng source SHA không đảm bảo cùng checked-out tree. Hai push jobs tương ứng với hai cặp successful tiêu tốn 2.867 runner-seconds (47:47); đây là cơ hội giảm công việc khi chuyển sang PR verification, không phải bằng chứng hai phép kiểm tra hoàn toàn tương đương.

## Phát hiện quan trọng

1. **P0 compatibility:** CI disposable dùng schema tạo mới hoặc Alembic upgrade; không chứng nhận hosted database. Không coi CI xanh là quyền tự động migrate.
2. **P0 baseline không xanh:** group mention ở `frontend/tests/fullstack/v3.spec.ts:150` mong `@Nhật ký tuần này mình thế nào?`, nhận `@Nhật ký uần này mình thế nào?t`. `GroupChat.tsx` cập nhật caret trong `requestAnimationFrame`; đây là giả thuyết race cần trace/reproduce, chưa phải nguyên nhân được chứng minh. Không bỏ assertion hoặc tăng retry để che lỗi.
3. **P1 critical path:** một job `verify`, tất cả steps chạy tuần tự. Pytest chiếm phần lớn backend; Vitest rất nhỏ. Ưu tiên chạy các lane độc lập trước khi giảm tests.
4. **P1 classification:** split bằng `-m postgres` hiện sẽ chuyển nhầm 154 database cases sang lane không có DB. Fixture còn drop/create toàn bộ ORM schema ở mỗi lần dùng, nhưng chưa có setup-duration evidence để định lượng phần tiết kiệm.
5. **P1 provenance:** publisher kiểm tra đúng current main/push/workflow ID/path/repository, recheck SHA, digest, attestations. Poller kiểm chứng lại manifest/OCI provenance. Phải giữ các invariant này khi đổi DAG.
6. **P2 maintenance:** 39 merge-readiness + 69 ux-redesign + 29 real UI cases có giao nhau về khu vực sản phẩm; nhiều case là race/keyboard/accessibility riêng. Không suy từ số file thành redundant behavior.
7. **P1 manual publish lookup:** khi manual dispatch chưa có CI_RUN_ID, workflow gọi `gh api .../runs -f ...` mà thiếu `--method GET`. CLI chuyển request có fields thành POST; đây là lỗi command được suy từ source + CLI semantics, chưa thử dispatch/publish thật. Plan yêu cầu mock test và sửa method, giữ toàn bộ exact-main filters.

## Quyết định thiết kế và các lựa chọn

Đề xuất của audit: giữ nguyên bố trí source phần lớn; chuẩn hóa metadata và ownership; tách CI thành lane có DB riêng, gate tổng hợp `verify`, full regression trên main; sau đó mới bật dependency-based selection trên PR. Không có lựa chọn nào được trình bày như người dùng đã phê duyệt implementation.

| Cách tiếp cận | Đánh đổi | Quyết định |
|---|---|---|
| Dọn/xóa tests trước | Nhanh trên giấy, chưa biết bottleneck hay parity; rủi ro privacy và race regressions | Không chọn |
| Đo → taxonomy → lane song song → selection → release compatibility | Có các checkpoint đo và rollback; thêm setup/runner cost | **Khuyến nghị** |
| Rewrite toàn bộ thư mục/fixture, sharding mọi suite | Diff lớn, khó phân biệt thay đổi semantics với tốc độ | Chỉ thử nghiệm nhỏ khi có profiling |

## Ưu tiên và tác động

Mọi con số mục tiêu dưới đây là **ESTIMATE**, chưa có workflow refactor để benchmark.

| Change | Priority | Expected impact | Risk | Effort/complexity |
|---|---|---|---|---|
| Preflight schema/runtime + image identity, giữ readiness | P0 | Ngăn deploy candidate sai schema; không nhắm giảm CI | Trung bình | 3–5 ngày kỹ thuật, cao |
| Điều tra HEAD failure và lập baseline sạch | P0 | Tránh đo trên suite đang không ổn định | Thấp nếu giữ assertions | 0,5–2 ngày; có thể cần bugfix riêng |
| Bỏ feature push khi đã chọn PR; PR concurrency | P1 | Bớt duplicate runner work; không rút ngắn một run đơn lẻ | Thấp–trung bình | 0,5–1 ngày |
| Tách các lane độc lập, giữ gate `verify` | P1 | Full verification median mục tiêu 11–15 phút | Trung bình | 2–4 ngày |
| Chuẩn hóa markers và helper ownership | P1 | Split đúng, ít cascade khi sửa tests | Trung bình | 2–4 ngày |
| `npm ci --no-audit`, giữ explicit audit | P1 | Bỏ audit request lặp; tác động thời gian nhỏ | Thấp | <0,5 ngày |
| uv/BuildKit caches có đo overhead | P2 | Setup/package nhanh hơn, nhất là cold runners | Thấp–trung bình | 1–2 ngày |
| Dependency selection trên PR | P2 | Lane liên quan mục tiêu 3–7 phút; docs-only <2 phút | Cao nếu false negative | 2–4 ngày |
| Gộp browser cases hoặc đổi reset strategy | P2 | Chưa định lượng; chỉ sau parity/profiling | Cao | 2–5 ngày thử nghiệm |
| Playwright cache, xdist, reuse verified images trong publish | P3 | Chỉ chọn nếu net saving/trust boundary chứng minh được | Trung bình–cao | Không ưu tiên trước |

Không thay đổi: security/privacy/auth/18+/migration checks; fake-model required CI; owned disposable DB guards; exact-main provenance, immutable digests, attestation và publication hold; Linux poller validation; kiểm tra cả Docker packaging variants còn được hỗ trợ.

Không khuyến nghị: bật pytest-xdist trên cùng DB, song song full-stack trên cùng fixtures, skip integration chỉ theo extension, bỏ build-context tests để tiết kiệm vài chục giây, scheduled paid evaluations không có budget/target authorization.

## Lộ trình và tài liệu

P0 baseline/safeguards → P1 trigger cleanup → P2 taxonomy/ownership → P3 parallel/cache → P4 selection/tiering → P5 compatibility gates → P6 parity/benchmark/rollout. P5 có **priority P0 về rủi ro**, dù tên phase theo yêu cầu; có thể làm song song sau P0 và phải xong trước lần deploy tiếp theo. Không triển khai release candidate không tương thích trong khi chờ tối ưu CI.

- [01 — Inventory, candidates, feature coverage](01-test-suite-inventory.md)
- [02 — Baseline, logs, bottlenecks](02-ci-baseline-and-bottlenecks.md)
- [03 — Test architecture](03-target-test-architecture.md)
- [04 — CI architecture](04-target-ci-architecture.md)
- [05 — Production compatibility](05-production-compatibility-gates.md)
- [06 — Tasks triển khai](06-refactor-implementation-plan.md)
- [07 — Validation và benchmark](07-validation-and-benchmark-plan.md)
- [08 — Prompt handoff](08-agent-implementation-handoff.md)

Giới hạn: chưa đo per-test pytest setup trên Linux; chưa benchmark cache cold/warm có kiểm soát; chưa inspect EC2/container/image đang chạy, synthetic login hoặc Storage policies trên hosted project bằng runtime role; chưa run full local DB/browser/Docker suite. Local Windows không thay thế Node 22/Linux CI. Hai docs links có sẵn bị đứt được ghi trong inventory; audit chỉ bảo đảm links của bộ tài liệu mới.
