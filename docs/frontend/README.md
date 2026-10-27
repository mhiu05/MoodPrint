# Frontend

SPA dùng React 19, TypeScript 5.9, Vite và React Router; tên package `moodprint-web`. Phiên bản resolved nằm trong [package-lock.json](../../frontend/package-lock.json). Entry duy nhất: [main.tsx](../../frontend/src/main.tsx) → [RealApp.tsx](../../frontend/src/features/real/RealApp.tsx).

## Bản đồ route

| Route | Màn hình / trách nhiệm |
| --- | --- |
| `/assistants`, `/assistants/:botId` | Danh sách bot, conversation history, chat, tools/cards, voice |
| `/self` | Nhật ký và thống kê cảm xúc |
| `/profile` | Private profile items, khác hồ sơ tìm bạn |
| `/memory` | Memory đã duyệt và proposals |
| `/connect` | Discovery, matching profile, lời mời; query tab phục vụ điều hướng |
| `/messages` | Danh sách kết nối và nhắn tin |
| `/settings` | Consent, eligibility, AI data preferences, privacy, identity |
| `/admin/reports` | Moderation cho staff, theo session capability |
| `/auth/callback` | Callback recovery được auth flow xử lý; server phải trả SPA shell |

Route fallback điều hướng về assistants. Session/eligibility gate chạy trước tính năng cá nhân. Staff route trong UI không thay thế kiểm tra role ở backend.

## Tổ chức mã nguồn

- `features/real/RealApp.tsx`: `SessionRoot`, `Shell`, session/resource hooks và nhiều màn hình AI. Đây là boundary hiện tại; tài liệu không giả định đã tách thành store/router framework khác.
- `features/real/social/`: public profile editor, discovery, request card, human chat, SSE/polling.
- `features/real/activities/`: activity dock và projection của quiz/icebreaker/focus.
- `components/UI.tsx`: primitives dùng chung; `components/motion/` giữ motion policy.
- `api/`: BFF transport, stream validation, generated types.
- `companions/`: avatar/presentation, không phải business rules hoặc fake provider.

Đọc [data flow](data-flow.md), [UI và accessibility](ui-accessibility.md), [testing](testing.md). [Frontend README](../../frontend/README.md) giữ quickstart ngắn.
