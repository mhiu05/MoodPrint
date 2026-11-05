# Frontend

SPA dùng React 19, TypeScript 5.9, Vite và React Router; tên package `moodprint-web`. Phiên bản resolved nằm trong [package-lock.json](../../frontend/package-lock.json). Entry duy nhất: [main.tsx](../../frontend/src/main.tsx) → [RealApp.tsx](../../frontend/src/features/real/RealApp.tsx).

## Bản đồ route

| Route | Màn hình / trách nhiệm |
| --- | --- |
| `/assistants`, `/assistants/:botId` | Danh sách bot, conversation history, chat, tools/cards, voice |
| `/assistants/groups/new`, `/assistants/groups/:groupId` | Tạo nhóm và chat với nhóm trợ lý |
| `/self` | Nhật ký và thống kê cảm xúc |
| `/self/calendar`, `/self/memories`, `/self/entry/:id` | Lịch, dòng thời gian và trang nhật ký |
| `/profile` | Tài khoản, quyền dữ liệu, công tắc xử lý nhật ký và hỗ trợ |
| `/memory` | Memory đã duyệt và proposals |
| `/settings` | Alias chuyển về `/profile` |
| `/check-ins` | Lịch hỏi thăm; guest thấy yêu cầu tạo tài khoản |
| `/feedback`, `/admin/feedback` | Gửi góp ý và xem góp ý theo quyền staff |
| `/admin/reports` | Moderation cho staff, theo session capability |
| `/auth/callback` | Callback recovery được auth flow xử lý; server phải trả SPA shell |

Điều hướng chính chỉ gồm Trợ lý, Nhật ký, Tài khoản. Route social cũ (`/connect`, `/messages`, profile người khác, hoạt động đôi) đi qua fallback về assistants. Session/eligibility gate chạy trước tính năng cá nhân. Staff route trong UI không thay thế kiểm tra role ở backend.

## Tổ chức mã nguồn

- `features/real/RealApp.tsx`: `SessionRoot`, `Shell`, session/resource hooks và nhiều màn hình AI. Đây là boundary hiện tại; tài liệu không giả định đã tách thành store/router framework khác.
- `features/real/journal/`: trang nhật ký, lịch, timeline, media và trạng thái xử lý.
- Giao diện `social/`, `activities/` và Safety đã gỡ; backend social/matching/activities vẫn được giữ.
- `components/UI.tsx`: primitives dùng chung; `components/motion/` giữ motion policy.
- `api/`: BFF transport, stream validation, generated types.
- `companions/`: avatar/presentation, không phải business rules hoặc fake provider.

Đọc [data flow](data-flow.md), [UI và accessibility](ui-accessibility.md), [testing](testing.md). [Frontend README](../../frontend/README.md) giữ quickstart ngắn.
