# WS-01 — Audit codebase và nền migration

Ưu tiên P0. Độ phức tạp S: một sửa lỗi nhỏ, một ledger. Nhánh: PR đầu vào `main`; phần còn lại `mhiu05/feat-refactor-ws01-baseline`.

## 1. Mục tiêu và giá trị

Đưa `main` về trạng thái CI xanh để mọi PR sau có baseline tin cậy và pipeline release chạy được.

## 2. Hiện trạng đã xác minh

- `Verify local application` trên `main` **đỏ** ở hai commit gần nhất (`13903dcd`, `2d00c8d2`). Publish bị `skipped`. VERIFIED.
- Lỗi: `frontend/tests/fullstack/v3.spec.ts:188`, axe `scrollable-region-focusable` trên `.conversation-log`. 1 failed, 37 passed, trên CI và tái hiện ở local. VERIFIED.
- `RealApp.tsx` dòng 2082–2087 có `role="log" aria-live="off" tabIndex={0} aria-label=...`. `groups/GroupChat.tsx` dòng 304 không có. VERIFIED.
- Release cuối là `staging-0573af5b...`. VERIFIED.

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
| WS-01-T01 | P0 | Không | Nhánh `fix/group-log-a11y` từ `main`. Thêm `role="log" aria-live="off" tabIndex={0} aria-label="Cuộc trò chuyện nhóm"` vào `GroupChat.tsx:304` | Vùng cuộn dùng được bằng bàn phím. Live region của nhóm không đổi; xác minh không đọc hai lần | `python ../scripts/test_fullstack.py v3.spec.ts` từ `backend/` | Pass: 0 violation. Fail: còn `scrollable-region-focusable` |
| WS-01-T02 | P0 | T01 | PR vào `main`, chờ CI | `Verify local application` xanh; Publish chạy | `gh run list --branch main` | Pass: success trên SHA mới. Fail 3 lần theo 3 hướng: báo owner |
| WS-01-T03 | P0 | T02 | Merge `main` vào `mhiu05/feat-refactor` | Nhánh đồng bộ | `git rev-list --left-right --count origin/main...HEAD` | Pass: trái = 0 |
| WS-01-T04 | P1 | T03 | Tạo `evidence/execution.md`, mục G0 | Ghi SHA, link CI, số test | Đọc lại | Pass: có link run xanh |
| WS-01-T05 | P2 | T03 | Xác minh `backend/app/ai/routes.py` có được import không; chỉ ghi kết quả vào ledger | Biết file này có phải code chết | `rg "ai.routes\|from app.ai import routes" backend` | Pass: có kết luận. Không xóa |

## 11. An toàn và bảo mật

Sửa accessibility, không đổi quyền. Không nới axe, không skip test.

## 12. Test

Fullstack `v3.spec.ts`; CI đầy đủ.

## 13. Acceptance criteria

CI xanh trên `main`; Publish thành công; ledger có bằng chứng.

## 14. Phụ thuộc và blocker

Không. Release tự động sau CI xanh sẽ deploy bản này lên staging: đây là hành vi bình thường, không đổi profile.

## 15. Rollback

Revert PR.

## 16. Definition of Done

G0 đạt.

## 17. Ghi chú cho Grok

CI mất khoảng 35 phút; main đổi trong lúc chờ thì Publish bỏ qua bản cũ. Không merge liên tiếp khi chưa cần.
