# WS-10 — Đánh giá, hiệu năng và release

Ưu tiên P0. Độ phức tạp L: phụ thuộc credential và thao tác hosted. Nhánh `mhiu05/feat-refactor-ws10-release`. Quy trình ở [release-runbook](../grok-handoff/release-runbook.md).

## 1. Mục tiêu và giá trị

Sản phẩm chạy trên staging, ba kịch bản demo hoạt động, có đường rollback.

## 2. Hiện trạng đã xác minh

Pipeline release hoạt động (lần cuối 05/11/2026). Hosted 0029. Không có marker hold. `deploy.sh` bắt buộc `APP_ENV=production`. Caddyfile, compose không đổi theo release.

## 3. Khoảng trống

E2E ba kịch bản, access matrix, artifact SQL 0035, image C, cấu hình SSM, seed, release note.

## 4. Kiến trúc đề xuất

Thứ tự **C → SQL → F**, đơn giản hơn lần 0029 vì schema mới chỉ thêm bảng và nới CHECK: image cũ tương thích, C chỉ cần nhận thêm revision 0035.

## 5. Phạm vi

Trong: eval cuối, hiệu năng, tài liệu, release. Ngoài: thí điểm thật.

## 6. File và symbol bị ảnh hưởng

`backend/app/core/revisions.py`; `scripts/apply_supabase_review.py` (`UPGRADES`); `deploy/supabase/reviewed-sql/MANIFEST.json`; `deploy/README.md`, `deploy/aws/README.md`, `docs/supabase/migrations.md`, `deploy/runtime.env.example`, `README.md`, `ARCHITECTURE.md`, `PRODUCT.md`, `docs/verification.md`, `.github/workflows/verify.yml`.

## 7. File mới

`deploy/supabase/reviewed-sql/0035-review.sql`; `docs/moodprint-school-safety/evidence/release.md`.

## 8. API contract

Không đổi.

## 9. Dữ liệu và migration

Áp `0029 → 0035` lên hosted. Forward-only.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-10-T00 | P0 | Trước giai đoạn 6 | Preflight ở [runbook](../grok-handoff/release-runbook.md#bước-0-điều-kiện-trước): Supabase MCP, AWS MCP, Region, tên khóa SSM | Biết rõ thiếu gì trước khi đụng hosted | Theo runbook | Pass. Fail: báo owner |
| WS-10-T01 | P0 | WS-09 | `tests/fullstack/school-kb-{a,b,c}.spec.ts`, `school-showcase.spec.ts` | Chạy đúng [kịch bản](../demo/scenarios-KB-A-B-C.md) và [ca trình diễn](../demo/showcase-cases.md) với model giả | `python ../scripts/test_fullstack.py school-` | Pass: tất cả |
| WS-10-T02 | P0 | WS-03…08 | `tests/test_school_access_matrix.py` | Mọi route mới đủ 6 vai | `pytest -q tests/test_school_access_matrix.py` | Pass |
| WS-10-T03 | P0 | T01 | Chạy lại eval trên `holdout` bằng phần ngân sách còn lại | Đạt ngưỡng; tổng chi dưới 2,80 USD; lưu báo cáo | Runner live; `live-eval-spend.jsonl` | Pass |
| WS-10-T04 | P1 | T01 | Mở rộng `scripts/load_chat_memory.py` cho `troly` | Đạt bảng hiệu năng ở [10](../10-evaluation-and-quality-gates.md) | `--workers 1 --users 10` | Pass: một worker |
| WS-10-T05 | P0 | T01 | Cập nhật tài liệu, sửa đoạn lỗi thời ở [01 §10](../01-codebase-audit.md#10-tài-liệu-lỗi-thời-và-code-thừa) | `check_docs.py` pass | `python scripts/check_docs.py` | Pass |
| WS-10-T06 | P0 | Mọi migration | `UpgradePlan "0035"`, export SQL, `MANIFEST.json` | Review-only khớp export; 18 bảng RLS | `python scripts/apply_supabase_review.py --upgrade 0035`; `python scripts/check_reviewed_artifacts.py` | Pass |
| WS-10-T07 | P0 | T06 | Diễn tập trên snapshot chỉ cấu trúc, rollback transaction rồi commit | 8 kiểm tra pass; đồng thời ASGI C ready trên 0029 và 0035 | Theo runbook | Pass |
| WS-10-T08 | P0 | T07 | PR C từ `main`: `READY_REVISIONS` thêm 0035; sửa test ghim; merge | Staging chạy C, `/ready` 200 trên 0029 | `gh run list`; `curl .../health/ready` | Pass |
| WS-10-T09 | P0 | T08 | Cập nhật SSM qua AWS MCP theo runbook, ghi số version cũ | Chưa có hiệu lực tới khi deploy; không in giá trị | So tên khóa trước và sau | Pass |
| WS-10-T10 | P0 | T09 | Áp SQL nguyên văn qua Supabase MCP theo runbook, chạy bộ truy vấn kiểm tra, ghi `0035-execution.json` | Revision 0035; `/ready` 200 trên C | Runbook bước 5 | Pass: mọi kiểm tra đúng. Lỗi: báo owner |
| WS-10-T11 | P0 | T10 | Sync `main`, PR `mhiu05/feat-refactor` → `main`; `READY_REVISIONS` chỉ 0035 | CI xanh; merge; Publish; poller deploy; `/ready` 200 | `gh run watch`; `curl` | Pass. Fail: rollback |
| WS-10-T12 | P0 | T11 | `seed_school_demo.py --apply` với năm persona, hồ sơ mẫu; chờ `sync` KB | Tài khoản hoạt động; thẻ đủ | Kiểm tra `kb_cards` count | Pass |
| WS-10-T13 | P0 | T12 | Smoke KB-A/B/C và SC-01…SC-10 trên staging với **model thật**, ảnh chụp, video dự phòng; kiểm tra đăng ký đóng | Mọi ca đạt; ca xác suất chạy 3 lần; ghi chi phí | Playwright live hoặc checklist | Pass |
| WS-10-T14 | P0 | T13 | `evidence/release.md`: SHA, migration, flag, giới hạn, rollback; báo cáo cho owner | Đủ sáu điều kiện | Đọc lại | Pass |

## 11. An toàn và bảo mật

Không in DSN. Không đọc `backend/.env`. Không đưa SSM ra log. Staging giữ đăng ký đóng. Dữ liệu demo hư cấu. Staging chạy model thật, trong trần `AI_DAILY_BUDGET_USD`.

## 12. Test và dataset

Như trên.

## 13. Acceptance criteria

Sáu điều kiện "Released" ở [runbook](../grok-handoff/release-runbook.md#1-released-nghĩa-là-gì).

## 14. Phụ thuộc và blocker

OD-02 (nội dung đã duyệt), OD-05. AWS MCP phải hoạt động.

## 15. Rollback

Theo runbook. Image C là đích rollback sau F.

## 16. Definition of Done

G5 đạt.

## 17. Ghi chú cho Grok

Merge tuần tự: CI 35 phút; nếu `main` đổi giữa chừng, Publish bỏ qua. Trước T11 phải chắc schema đã 0035, nếu không F sẽ fail health và tự rollback. `workflow_dispatch` chỉ chạy khi actor là chủ repo.
