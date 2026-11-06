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
| WS-10-T01 | P0 | WS-09 | `tests/fullstack/school-kb-{a,b,c}.spec.ts` | Chạy đúng [kịch bản](../demo/scenarios-KB-A-B-C.md) với model giả | `python ../scripts/test_fullstack.py school-kb` | Pass: cả ba |
| WS-10-T02 | P0 | WS-03…08 | `tests/test_school_access_matrix.py` | Mọi route mới đủ 6 vai | `pytest -q tests/test_school_access_matrix.py` | Pass |
| WS-10-T03 | P0 | T01 | Chạy lại eval an toàn, KB, luyện nói trên holdout | Đạt ngưỡng; lưu báo cáo | Runner live | Pass |
| WS-10-T04 | P1 | T01 | Mở rộng `scripts/load_chat_memory.py` cho `troly` | Đạt bảng hiệu năng ở [10](../10-evaluation-and-quality-gates.md) | `--workers 1 --users 10` | Pass: một worker |
| WS-10-T05 | P0 | T01 | Cập nhật tài liệu, sửa đoạn lỗi thời ở [01 §10](../01-codebase-audit.md#10-tài-liệu-lỗi-thời-và-code-thừa) | `check_docs.py` pass | `python scripts/check_docs.py` | Pass |
| WS-10-T06 | P0 | Mọi migration | `UpgradePlan "0035"`, export SQL, `MANIFEST.json` | Review-only khớp export; 18 bảng RLS | `python scripts/apply_supabase_review.py --upgrade 0035`; `python scripts/check_reviewed_artifacts.py` | Pass |
| WS-10-T07 | P0 | T06 | Diễn tập trên snapshot chỉ cấu trúc, rollback transaction rồi commit | 8 kiểm tra pass; đồng thời ASGI C ready trên 0029 và 0035 | Theo runbook | Pass |
| WS-10-T08 | P0 | T07 | PR C từ `main`: `READY_REVISIONS` thêm 0035; sửa test ghim; merge | Staging chạy C, `/ready` 200 trên 0029 | `gh run list`; `curl .../health/ready` | Pass |
| WS-10-T09 | P0 | T08, OD-01, OD-12 | Owner cập nhật SSM theo danh sách ở runbook | Chưa có hiệu lực tới khi deploy | Owner xác nhận | **Cần owner** |
| WS-10-T10 | P0 | T09 | Áp SQL hosted | Revision 0035; `/ready` 200 trên C | `apply_supabase_review.py --upgrade 0035 --apply ...` | Pass: report JSON. Lỗi: báo owner |
| WS-10-T11 | P0 | T10 | Sync `main`, PR `mhiu05/feat-refactor` → `main`; `READY_REVISIONS` chỉ 0035 | CI xanh; merge; Publish; poller deploy; `/ready` 200 | `gh run watch`; `curl` | Pass. Fail: rollback |
| WS-10-T12 | P0 | T11 | `seed_school_demo.py --apply`, chờ `sync` KB, `check` | Tài khoản hoạt động; thẻ đủ | Kiểm tra `kb_cards` count | Pass |
| WS-10-T13 | P0 | T12 | Smoke KB-A/B/C trên staging, ảnh chụp; kiểm tra đăng ký đóng | Ba kịch bản đạt | Playwright live hoặc checklist | Pass |
| WS-10-T14 | P0 | T13 | `evidence/release.md`: SHA, migration, flag, giới hạn, rollback; báo cáo cho owner | Đủ sáu điều kiện | Đọc lại | Pass |

## 11. An toàn và bảo mật

Không in DSN. Không đọc `backend/.env`. Không đưa SSM ra log. Staging giữ đăng ký đóng. Dữ liệu demo hư cấu.

## 12. Test và dataset

Như trên.

## 13. Acceptance criteria

Sáu điều kiện "Released" ở [runbook](../grok-handoff/release-runbook.md#1-released-nghĩa-là-gì).

## 14. Phụ thuộc và blocker

OD-01, OD-02, OD-04, OD-05, OD-11, OD-12.

## 15. Rollback

Theo runbook. Image C là đích rollback sau F.

## 16. Definition of Done

G5 đạt.

## 17. Ghi chú cho Grok

Merge tuần tự: CI 35 phút; nếu `main` đổi giữa chừng, Publish bỏ qua. Trước T11 phải chắc schema đã 0035, nếu không F sẽ fail health và tự rollback. `workflow_dispatch` chỉ chạy khi actor là chủ repo.
