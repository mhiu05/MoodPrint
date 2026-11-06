# Mẫu PR

Nhánh con tách từ `mhiu05/feat-refactor` mới nhất, ví dụ `mhiu05/feat-refactor-ws03-safety`. PR vào `mhiu05/feat-refactor`, trừ PR sửa `main` ở WS-01 và các bước release.

```markdown
## Task

WS-XX-Tnn, WS-XX-Tmm

## Thay đổi

- <điều gì đổi, vì sao>

## Test đã chạy

| Lệnh | Kết quả thật |
| --- | --- |
| `uv run --locked pytest -q tests/...` | N passed, M failed, thời gian |
| `npm test` | |

Không chạy: <liệt kê và lý do>.

## Ảnh UI

Mobile 360px: <ảnh>
Desktop 1280px: <ảnh>

(Bỏ mục này nếu không đổi giao diện.)

## Migration

Revision: <tên hoặc Không>
`alembic check`: <kết quả>
Tương thích image cũ: <có/không, lý do>

## An toàn

- Nội dung có vào log không?
- Có hành động bền vững nào không qua xác nhận người dùng không?
- Có đường gọi model mới không? Có ngân sách, timeout, fallback chưa?

## Rủi ro

<rủi ro còn lại>

## Rollback

<cách quay lại>

## Gate

Gate liên quan: <G1...>; trạng thái: <đạt / chưa>.
```

## Trước khi merge

- [ ] CI `Verify local application` xanh trên đúng SHA.
- [ ] Không còn TO_VERIFY cho phần đã làm.
- [ ] `docs/moodprint-school-safety/11-master-implementation-roadmap.md` đã cập nhật trạng thái.
- [ ] Ledger `evidence/execution.md` có dòng mới.
- [ ] Không có secret, DSN, nội dung người dùng trong diff.
