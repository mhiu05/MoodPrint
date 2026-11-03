# Per-Agent Check-in Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans hoặc superpowers:subagent-driven-development để triển khai task-by-task. Đây là di chuyển UI, không thay lịch/backend scheduler.

**Goal:** Người dùng quản lý lịch hỏi thăm sáng/tối của mỗi agent ngay trong nút thông tin của agent, bỏ mục lịch khỏi Tài khoản và trang quản lý tập trung không còn cần thiết.

**Architecture:** Tách các control lịch hiện có thành components/hook tái sử dụng; gắn vào `ConversationInfo` theo agent identity. Giữ nguyên `/ai/proactive` DTO/endpoints và global settings duy nhất cho timezone/quiet/badges/journal-context. Inbox/lịch sử không phụ thuộc trang settings và tiếp tục ở luồng chat/assistant roster.

**Tech Stack:** React/TypeScript, UI/Dialog/CSS hiện có, FastAPI proactive API không đổi trong phase chính.

**Spec:** [00](00-overview.md), [01](01-codebase-audit.md), phối hợp journal help copy với [05](05-collaboration-defaults.md).

## Global Constraints

- Không bật/tắt/chuyển/xóa lịch chỉ vì mở panel hoặc nâng phiên bản UI. Defaults lịch mới vẫn off.
- Giữ schedule rows/versions, eligibility, quiet hours, timezone, daily cap, weekday/custom repeat, pause/resume/auto-pause, legacy migration và backend rules.
- Không di chuyển timezone thành setting riêng của từng agent; không đổi giờ UTC/local hay tính `nextDeliveryAt` trong frontend thay server.
- Giữ `/ai/inbox`, unread/read markers, proactive origin/slot labels, delivered chat history và worker.
- Account không còn “Lời hỏi thăm từ trợ lý” hoặc link quản lý lịch; không thay account age/security/data controls.

## UX và ranh giới agent/global

Trong info panel hiện có, thêm section **“Lời hỏi thăm của {agent}”** sau mô tả agent, trước các hành động quản lý conversation. Chỉ hiện hai slots của `botId` đó: bật/tắt, giờ, ngày lặp, pause/tiếp tục, next delivery và lỗi; giữ control xóa lịch của agent nếu đã có. Label chỉ rõ schedule dùng cho agent qua mọi conversation. Panel mở được cả trước tin nhắn đầu tiên, không bắt tạo chat để chỉnh lịch.

`ConversationInfo` nhận `botId: BotId` và slot nội dung `agentSettings?: ReactNode`. Identity mặc định là owner của màn `/assistants/:botId`, **không đổi theo `message.speaker` hoặc `active_agent`**. Nếu đang handoff, banner có action mở thông tin specialist bằng route của chính specialist; không lấy lịch Điều phối hiển thị dưới tên Hoạt động. Group info không nhận lịch “group” hoặc nhân bản lịch từng member; người dùng mở agent riêng từ member roster.

Phần **“Dùng chung cho mọi trợ lý”** trong panel mở editor global settings dùng chung: timezone, quiet hours, badge. Timezone hiện tại luôn thấy ở lịch; action “Đổi múi giờ dùng cho tất cả trợ lý” giải thích rằng giờ địa phương các lịch được giữ và thời điểm UTC kế tiếp được server tính lại. Trước lưu editor cho thấy agent/slots nào chịu ảnh hưởng (từ `ProactiveView` đang có), không lặng lẽ tạo3 bản timezone. Server vẫn từ chối quiet-hour mới đè vào một lịch đang bật, kể cả lịch của agent khác; UI phải đưa link mở đúng lịch xung đột.

Journal-context toggle chỉ quản lý trong info Nhật ký (Nhịp khi legacy mode), giữ value/version cũ và helper đủ chính xác về các usage đang có. Điều phối/Hoạt động muốn xem điều kiện journal-context có link tới info Nhật ký, không copy toggle ở nhiều panel. Khi05 defaults active, help giải thích hợp tác có thể dùng tóm tắt trong giới hạn hiện có; không mô tả là bật lịch hay cho mọi agent xem nguyên văn. Không tự bật consent hoặc đổi `policyVersion` khi di chuyển UI. Nếu cần thay ý nghĩa consent vượt phạm vi đang có, phải tách thành quyết định/migration khác, ngoài plan di chuyển này.

State đủ: loading, chưa có lịch, enabled, disabled, paused-until, auto-paused, ineligible/history/provider unavailable, cap reached ở agent khác, saving, saved, stale409, network/offline/error. Tải settings khi panel mở; fetch lỗi chỉ chặn schedule controls, chat/info khác vẫn dùng được. Mở/đóng panel không gửi PUT. Autosave/version handling theo control hiện có; không optimistic “đã lưu” trước server response.

## Audit và xử lý route `/check-ins`

Source hiện tại xác nhận `/check-ins` chỉ render `CheckInsPage` quản lý lịch, không inbox lịch sử. Inbox thật ở assistant roster + `useAIInbox`, delivered messages trong chat. Vì vậy **bỏ trang schedule tập trung** sau khi controls đã được trích sang panel; không xóa proactive/inbox APIs, models, jobs hoặc messages.

- Link trong proactive bubble “Đổi hoặc tắt lời hỏi thăm này” chuyển tới `/#/assistants/<botId>?panel=info&section=check-ins`; mở/focus đúng section sau load. Route đang dùng HashRouter nên search params thuộc hash route, không dùng fragment thứ hai.
- Giữ compatibility redirect `/check-ins?bot=<id>` → agent đó mở info/check-ins. `/check-ins` không bot → `/assistants?manageCheckIns=1`, roster có action mở info của agent, không đưa lại menu Account. Invalid ID về roster có thông báo, không fetch schedule của người khác.
- Legacy schedules vẫn lưu. Info successor có mục thu gọn “Lịch cũ” trỏ tới panel legacy giữ nguyên giờ/trạng thái, cho chuyển/xóa bằng endpoint hiện tại và hành động rõ của người dùng; không tự migrate. Legacy Cầu Nối không successor: compatibility route mở view legacy chỉ để xem/tắt/xóa lịch, không biến thành agent V3 mới. Có thể giữ adapter route/component cho legacy nhưng không giữ lại trang quản lý tổng hợp cũ.
- Bỏ `CheckInsSummary` khỏi AccountPage và các link quản lý tương đương. Giữ link/chat unread từ các entry point khác; không tạo inbox mới nếu chưa cần.

## Interfaces và files

Không cần migration dữ liệu hoặc API endpoint mới cho thay UI này. Giữ:

```text
GET /ai/proactive -> ProactiveView
PUT /ai/proactive/schedules/{bot_id}/{morning|evening} -> ScheduleView
DELETE cùng route, body expectedVersion -> ActionReceipt
POST /ai/proactive/schedules/{bot_id}/{slot}/migrate
PUT /ai/proactive/settings -> ProactiveSettingsView
```

Resume = cập nhật schedule với `pausedUntil:null` hoặc bật lại auto-paused theo semantics hiện có, không tạo endpoint resume mới. Slot version và global settings version độc lập; cap lấy `limits.dailyCap/enabledSlots` toàn tài khoản từ server, không đếm riêng2 slots trong panel.

Tạo `frontend/src/features/real/checkins/{AgentCheckInSettings,CheckInSlot,SharedCheckInSettings,LegacyCheckInSettings}.tsx`, `useProactiveSettings.ts`, `useProactiveSettings.test.ts`. Hook nhận `ApiClient` từ parent và shared state theo user, tránh thêm circular import về RealApp; dùng chung model helpers trong `checkinsModel.ts`. Di chuyển `SlotRow/QuietHours/ZoneDialog` và save/migrate/remove logic từ `CheckInsPage.tsx`, không clone ba bản.

Sửa `RealApp.tsx` (AccountPage/routes/proactive links/owner bot identity), `ConversationInfo.tsx`, `agent-chat.css`, `checkins/{checkins.css,proactive.css}`, các links explanation05; `orchestration/AgentLines.tsx` thêm action info specialist. Để rollout UI có cờ server, sửa tối thiểu `backend/app/core/config.py`, `backend/app/contracts.py`, `backend/app/modules/auth/routes.py` và sinh lại contracts; không đổi proactive DTO. `CheckInsPage.tsx` xóa khi hết imports, hoặc thu nhỏ chỉ redirect adapter sau full rollout. `useAIInbox.tsx`/backend proactive không đổi trừ tests phát hiện regression thật có liên quan trực tiếp.

## Tasks và tests tương lai

### K1 — Trích controller/controls và giữ contracts

**Interfaces:** `useProactiveSettings(api)` trả view/loading/status và `saveSchedule/saveSettings/migrate/remove`; components nhận schedule theo botId. Shared state giữ một source of truth cho toàn user.

- [x] Failing tests snapshot version0 tạo settings, optimistic rollback, fresh409 patch chỉ áp field vừa sửa, không replay toàn stale global body làm bật lại journal consent. Hai agent panels/tabs có timezone change không gây lệch settings.
- [x] Trích controls và hook, giữ request body/version/receipt behavior. Không tạo PUT khi load/mount; thay timezone refresh mọi next-delivery, cap lấy server.
- [x] Chạy `npx.cmd vitest run src/features/real/checkins/checkinsModel.test.ts src/features/real/checkins/useProactiveSettings.test.ts`; pass; chưa cần backend migration hay credential.

### K2 — Info panel theo agent và global editor

**Files:** ConversationInfo, RealApp và4 components mới; thêm E2E `frontend/tests/e2e/agent-check-in-settings.spec.ts`.

- [x] Fixture mỗi agent sáng/tối đúng botId, trước chat đầu tiên, handoffowner khácspeaker, cap4/toànuser, paused/auto-paused/next delivery, global setting affects all và journal toggle chỉ Nhật ký.
- [x] Nối info panel và shared editor; preserve desktop modeless và compact modal. Sửa focusable query hiện tại để bao gồm `select/textarea` cùng buttons/inputs/links; không phát minh focus trap trên desktop. Khi mở child modal, suspend compact info panel, restore đúng trigger khi đóng.
- [ ] Kiểm Escape, Tab/Shift+Tab cả select, radio/checkbox labels, status/error `aria-live`, scroll vào section,320/390/768/1099/1100/1280px, zoom200%, reduced motion/keyboard on phone. Resize giữa modal/modeless không để hai modal hoặc mất focus; contrast theo tokens hiện có.
- [x] Playwright targeted suite và axe fixture trên panel đang mở pass. Đã nhìn screenshots 320/1280 và 200% cỡ chữ; keyboard/resize/deep-link/quiet-hour focus/pause-resume được kiểm tự động. Chưa coi đây là manual screen-reader hay browser zoom QA; xem evidence phiên Independent review.

### K3 — Bỏ Account entry và chuyển routes/links

- [x] Failing E2E Account không có mục/check-in link; old URLs đi đúng info section; proactive bubble link, unread/inbox/open-chat vẫn làm việc; invalid ID và lịch legacy/Cầu Nối có đường quản lý an toàn.
- [x] Bỏ Summary/lazy page, thêm redirect compatibility và deep-link focus. Giữ legacy transfer/remove flow từ API hiện có; không upsert schedule lúc chuyển route.
- [x] Chạy `npx.cmd playwright test tests/e2e/agent-check-in-settings.spec.ts tests/e2e/proactive.spec.ts tests/e2e/chat-history.spec.ts`; pass bằng fixtures. Test schedule payload không đổi trước/sau chuyểnUI.

### K4 — Regression scheduler và rollout UI

- [x] Trong phiên triển khai, chạy `uv run --locked pytest tests/test_proactive_api.py tests/test_proactive_schedule.py tests/test_proactive_quiet_hours.py tests/test_proactive_lifecycle.py tests/test_proactive_privacy.py tests/test_v3_proactive.py -q` từ backend, DB disposable/fake. Mong đợi pass, không có diff schedule rows do UI-only release.
- [x] Quyết định cleanup release: bỏ manager/Account entry, old route redirect; panel dùng `features.proactive`, không tạo flag không còn chọn được vị trí UI. Chưa rollout staging/production. Ruling và yêu cầu rollback image pair ở dưới.
  - Ruling 2026-11-03 (continuation): the working tree had already removed the old manager and
    Account entry, so no compatibility release exists and `AI_AGENT_CHECK_IN_SETTINGS_ENABLED`
    could not select a placement (panel showed for `proactive OR flag`, opening the panel against
    a disabled proactive API). The dead flag was removed; the panel is gated by
    `features.proactive`, the same gate as the former Account entry. This tree ships as the
    cleanup release; rolling the UI back means restoring the previous compatible image pair.
- [ ] Rollback cờUI trong release compatibility, hoặc restore image compatibility sau release cleanup; giữ data/worker/các cờ proactive. Không toggle `PROACTIVE_WORKER_ENABLED` để rollback một thay đổi UI.

## Review Focus, failure, chi phí và acceptance

Global timezone bị clone theo agent → K1/K2 single source/version; handoff đổi nhầm schedule owner → K2 owner/speaker fixture; select không nằm tab loop → K2 keyboard/resize; route removal xóa inbox/legacy access → K3 journeys; stale settings bật lại journal consent → K1 concurrent fresh-patch test.

Không thêm model/tool cost, chỉ HTTP đọc/lưu settings khi cần; debounce/refetch theo visibility, không polling settings mỗi chat tick. Không thay timeout/backend failure rules; offline/stale giữ UI rõ và người dùng có thể retry đúng action. Privacy giữ nguyên saved schedules/consent/version và giới hạn context; URL chỉ chứa botId/public panel name, không giờ/địa chỉ/private text.

Acceptance: từng agent có toàn bộ chức năng lịch đang có trong info panel; Tài khoản không còn mục lịch; global timezone/quiet settings nhất quán; old routes, delivered history và inbox còn hoạt động; desktop/mobile/keyboard/focus có bằng chứng kiểm. AWS không cần credential mới hoặc IAM/migration; nếu chỉ dờiUI và proactive đang bật thì không cần đổi cờ worker. Nếu staging chưa bật proactive, chỉ enable theo runbook có sẵn và [07](07-rollout-credentials-and-coverage.md), giữ mọi lịch off/on hiện có.
