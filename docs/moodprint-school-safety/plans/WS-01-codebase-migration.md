# WS-01 — Audit codebase và nền migration

Ưu tiên P0. Độ phức tạp S: một sửa lỗi nhỏ, một ledger. Nhánh `mhiu05/feat-refactor`.

## 1. Mục tiêu và giá trị

Đưa `mhiu05/feat-refactor` về trạng thái CI xanh để mọi commit sau có baseline tin cậy.

## 2. Hiện trạng đã xác minh

- `Verify local application` trên `main` **đỏ** ở hai commit gần nhất (`13903dcd`, `2d00c8d2`). Publish bị `skipped`. VERIFIED.
- Lỗi: `frontend/tests/fullstack/v3.spec.ts:188`, axe `scrollable-region-focusable` trên `.conversation-log`. 1 failed, 37 passed, trên CI và tái hiện ở local. VERIFIED.
- `RealApp.tsx` dòng 2082–2087 có `role="log" aria-live="off" tabIndex={0} aria-label=...`. `groups/GroupChat.tsx` dòng 304 không có. VERIFIED.
- Release cuối là `staging-0573af5b...`. VERIFIED.
- Bản sửa đã vào `main` qua PR #45 ngày 06/11/2026, trước khi quy tắc nhánh đổi. `mhiu05/feat-refactor` chưa có bản sửa, nên CI nhánh còn đỏ ở bước fullstack. VERIFIED.

## 3. Khoảng trống

Chưa có ledger thực thi cho chương trình này. Tài liệu vận hành có đoạn lỗi thời ([01 §10](../01-codebase-audit.md#10-tài-liệu-lỗi-thời-và-code-thừa)), sửa ở WS-10.

## 4. Kiến trúc đề xuất

Không có. Chỉ sửa lỗi và chuẩn hóa cách ghi bằng chứng.

## 5. Phạm vi

Trong: sửa CI, ledger, xác nhận đồng bộ nhánh. Ngoài: mọi tính năng.

## 6. File và symbol bị ảnh hưởng

`frontend/src/features/real/groups/GroupChat.tsx:304`.

## 7. File mới

`docs/moodprint-school-safety/evidence/execution.md`: ledger theo thứ tự thời gian.

## 8. API contract

Không đổi.

## 9. Dữ liệu và migration

Không đổi.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-01-T01 | P0 | Không | **Đã xong** qua PR #45, commit `6d2662d6`, merge vào `main` ở `8b329980`. Không làm lại | `.conversation-log` có `role="log"`, `tabIndex`, `aria-label` | `gh pr view 45` | Pass |
| WS-01-T02 | P0 | T01 | Trên `mhiu05/feat-refactor`: `git fetch`, merge `origin/main` vào nhánh, push. Không tạo nhánh mới, không mở PR | Nhánh có bản sửa của PR #45 | `git rev-list --left-right --count origin/main...HEAD` | Pass: trái = 0 |
| WS-01-T03 | P0 | T02 | Chờ CI trên `mhiu05/feat-refactor` | `Verify local application` xanh | `gh run list --branch mhiu05/feat-refactor` | Pass: success trên SHA mới. Fail 3 lần theo 3 hướng: báo owner |
| WS-01-T04 | P1 | T03 | Tạo `evidence/execution.md`, mục G0 | Ghi SHA, link CI, số test | Đọc lại | Pass: có link run xanh |
| WS-01-T05 | P2 | T03 | Xác minh `backend/app/ai/routes.py` có được import không; chỉ ghi kết quả vào ledger | Biết file này có phải code chết | `rg "ai.routes\|from app.ai import routes" backend` | Pass: có kết luận. Không xóa |

## 11. An toàn và bảo mật

Sửa accessibility, không đổi quyền. Không nới axe, không skip test.

## 12. Test

Fullstack `v3.spec.ts`; CI đầy đủ.

## 13. Acceptance criteria

CI xanh trên `mhiu05/feat-refactor`; ledger có bằng chứng.

## 14. Phụ thuộc và blocker

Không. Release tự động sau CI xanh sẽ deploy bản này lên staging: đây là hành vi bình thường, không đổi profile.

## 15. Rollback

Revert commit.

## 16. Definition of Done

G0 đạt.

## 17. Ghi chú cho Grok

CI mất khoảng 35 phút; main đổi trong lúc chờ thì Publish bỏ qua bản cũ. Không merge liên tiếp khi chưa cần.
