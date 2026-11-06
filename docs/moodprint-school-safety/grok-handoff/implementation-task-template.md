# Mẫu task

Dùng khi Grok cần chia nhỏ thêm một task hoặc thêm task mới. Task phải nhỏ, kiểm thử được, không cần thiết kế lại.

```markdown
### WS-XX-Tnn: <tên ngắn>

**Ưu tiên**: P0 | P1 | P2
**Phụ thuộc**: <ID task>
**Thay đổi**: <cụ thể>
**Ở đâu**: <file, symbol; đường dẫn chưa chắc ghi TO_VERIFY>
**Hành vi mong đợi**: <quan sát được>
**Test**: <tên file, tên test>
**Lệnh**: <lệnh chạy>
**Pass**: <điều kiện>
**Fail**: <điều kiện và cách xử lý>
```

## Quy trình mỗi task

1. Viết test thất bại trước. Chạy để thấy nó fail đúng lý do.
2. Viết code tối thiểu.
3. Chạy test, rồi các test lân cận.
4. Nếu thêm route: cập nhật `docs/backend/api-reference.md`, chạy export OpenAPI, sinh TS.
5. Nếu thêm setting: cập nhật `docs/backend/configuration.md` và ba file env example.
6. Nếu thêm bảng: cập nhật `docs/supabase/schema.md`, export, purge.
7. Commit nhỏ, thông điệp tiếng Anh theo Conventional Commits như lịch sử repo.

## Cấm

- Task mơ hồ như "refactor hệ thống AI", "cải thiện UX".
- Sửa test để qua CI mà không có thay đổi hành vi theo plan.
- `skip`, `xfail`, nới ngưỡng, xóa assert.
- Thêm thư viện ngoài danh sách trong plan mà không ghi lý do trong commit.
- Ghi tên hoặc dữ liệu người thật vào fixture.
