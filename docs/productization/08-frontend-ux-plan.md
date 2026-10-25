# 08 — Frontend UX/UI Plan

Scope: the production React app in `frontend/src/features/real/`. Keep the existing visual language (tokens in `styles/tokens.css`, `components/UI.tsx` primitives `Button`, `Dialog`, `StatePanel`, `Motion`, `Typing`, `Brand`), Vietnamese copy, HashRouter routes and the shell (rail on ≥ 768 px, bottom nav on < 768 px, full-screen conversations on mobile). Do not redesign working AI/mood/privacy screens.

Breakpoints (existing CSS): **< 768 px** mobile · **768–1099 px** tablet · **≥ 1100 px** desktop. Acceptance sizes: 390 × 844, 430 × 932, 768 × 1024, 1280 × 900, 1440 × 960, plus 390 × 480 for the keyboard-open case.

## 1. Journey and screens

| # | Step | Route | Screen / component | Change |
|---|---|---|---|---|
| 1 | Signup / login | `/` (unauth) | `Auth.tsx` | none |
| 2 | Age declaration | `/` | `Eligibility.tsx` | none |
| 3 | Self-discovery | `/assistants`, `/self`, `/memory`, `/profile` | existing | add a soft nudge card on `/assistants` after first AI turn: "Sẵn sàng tìm người cùng tần số? Tạo hồ sơ kết nối" → `/connect?tab=profile` (only if adult + MATCH not yet published) |
| 4 | Publish matching profile | `/connect?tab=profile` | `ProfileEditor` (stepper) | **new** |
| 5 | Discovery | `/connect?tab=suggestions` | `Discovery` + `CandidateCard` | **redesign** |
| 6 | Requests | `/connect?tab=requests` | `RequestCard` (sender card) | **redesign** |
| 7 | Connection list | `/messages` | `HumanMessages` with unread/preview | **enhance** |
| 8 | Human chat | `/chat/:connectionId` | `HumanChat` + `ActivityDock` | **enhance** |
| 9 | Shared activity | inside chat | activity panels | **new** |
| 10 | Continue conversation | chat | summary card → composer focus | **new** |
| — | Moderation (staff) | `/admin/reports` | `admin/Moderation.tsx` | **new**, hidden unless `session.staff` |

## 2. Navigation

- Primary nav (unchanged order): Trợ lý · Tìm bạn · Tin nhắn · Tôi.
- Badges (from `GET /social/summary`, polled every 15 s while visible, refreshed on focus): **Tìm bạn** shows pending incoming requests; **Tin nhắn** shows unread connections + activity invites. Badge = dot + count (max "9+"), `aria-label` e.g. "Tin nhắn, 2 cuộc trò chuyện chưa đọc".
- Discovery uses tabs (`role="tablist"`): Gợi ý · Lời mời (count) · Hồ sơ kết nối. Tab state lives in the URL query (`?tab=`), so back/refresh keep it.

## 3. Component structure

```
features/real/social/
  Discovery.tsx          tabs container, gates (feature off / under 18 / MATCH off)
  ProfileEditor.tsx      stepper: Sở thích → Giá trị → Cách trò chuyện & mục tiêu → Hoạt động & thời gian → Xem trước
  TagPicker.tsx          grouped chips by category; min/max counters; keyboard operable (checkbox semantics)
  CandidateCard.tsx      avatar seed, alias, matchLabel chip, ≤3 reason chips, tags, activities; actions
  RequestCard.tsx        incoming/outgoing variants with PeerCard and decisions
  HumanMessages.tsx      list rows: alias, preview, relative time, unread badge, activity indicator
  HumanChat.tsx          header, log, inline activity cards, composer, dock host
  useConnectionEvents.ts SSE + polling fallback (moved from HumanChat)
  useSocialSummary.ts
features/real/activities/
  ActivityEntryButton.tsx  "Cùng làm gì đó?" next to composer
  ActivityCatalog.tsx      sheet listing definitions (title, minutes, description) + focus options
  InviteCard.tsx           inline log card; inviter/invitee variants
  ActivityDock.tsx         sheet (< 1100) / side panel (≥ 1100); collapsed bar
  IcebreakerPanel.tsx  QuizPanel.tsx  FocusPanel.tsx  FocusTimerChip.tsx
  ActivitySummary.tsx  FeedbackChips.tsx
  useActivity.ts  clock.ts  activities.css
```

## 4. Discovery screens

**Profile editor (stepper).** One facet group per step on mobile; all steps visible as an accordion on desktop. Each step shows counters ("Đã chọn 2/3 tối thiểu"). Step 5 "Xem trước" renders exactly the public card others will see, then **Xuất bản hồ sơ**. If a live profile exists, the editor opens prefilled; republishing shows an info line: "Các kết nối hiện có vẫn được giữ" (DR-03). Withdraw lives here with a confirmation dialog.

**Suggestions.** Up to 5 `CandidateCard`s. Card actions: primary **Gửi lời chào**, secondary **Bỏ qua**, overflow (⋯) **Chặn** (confirmation dialog). After sending: card shows "Đã gửi lời chào" and stays until refresh. A footnote under the list explains: "Gợi ý dựa trên những điểm chung bạn và họ tự chọn chia sẻ — không phải đánh giá mức độ hợp nhau." States: loading skeleton (3 cards), empty (honest copy + actions: bật nhận cả mục tiêu khác, thêm ngôn ngữ, thêm sở thích), error (retry), profile missing/stale (CTA to editor), MATCH off (link to settings).

**Requests.** Incoming card shows the sender's `PeerCard` and **Đồng ý kết nối** / **Từ chối**; outgoing shows the recipient's card with **Hủy lời mời** and expiry ("còn 5 ngày"). Terminal requests collapse into a "Đã xử lý" section (last 10).

## 5. Messages list and chat

**List row:** alias (bold if unread), last message preview prefixed "Bạn: " when self, relative time, unread count badge, small activity icon when an activity is live/invited. Sorted by `lastMessageAt` desc (fallback `createdAt`). Empty: "Chưa có cuộc trò chuyện" + link to suggestions.

**Chat header:** back (mobile), alias, overflow menu: Chia sẻ thông tin (reveal), Báo cáo, Chặn, Kết thúc kết nối. On mobile the header stays fixed; the log scrolls; composer sits above the safe area.

**Read markers:** when the newest message is visible and the tab is visible, call `POST /connections/{id}/read` (debounced 1 s). No read receipts are shown to the peer.

**PII advisory (I-06):** if the draft matches phone/email/URL patterns, the first send opens a dialog: "Tin nhắn có vẻ chứa thông tin liên hệ. Bạn chắc chắn muốn chia sẻ?" with **Sửa lại** / **Vẫn gửi**. Non-blocking, client-side only.

## 6. Shared activity interaction (both screens)

Dock behavior: mobile/tablet bottom sheet (expanded ≈ 60 % viewport height, drag handle, "Thu gọn" button; collapsed 56 px bar above the composer). Desktop: right side panel 380 px; the chat log narrows. Opening/closing preserves the composer draft and focus returns to the trigger.

### 6.1 Invite

| Step | Inviter | Invitee |
|---|---|---|
| Open catalog | Taps "Cùng làm gì đó?" → sheet with 3 cards (Câu hỏi làm quen · Đố vui đồng đội · Cùng tập trung) | — |
| Send | Chooses card (Focus: plan + cycles) → **Mời cùng chơi**; sheet closes; inline `InviteCard` "Đang chờ {alias}… · Hủy" | Inline `InviteCard` appears (≤ 2 s) with **Đồng ý** / **Để sau**; the list row shows the activity icon |
| Accept | Dock opens automatically | Dock opens |
| Decline | Card: "{alias} chưa muốn chơi lúc này"; entry button disabled 10 min for that kind with tooltip | Card collapses |

### 6.2 Icebreaker panel

Progress "Câu 1/3" + 3 dots; question prompt (`h3`, focus target); option radios (≥ 44 px rows) + optional text field (140 chars, counter); **Gửi câu trả lời** and **Bỏ qua câu này**. After submit: own answer shown read-only, status line "Đang chờ {alias}…" (`role="status"`). On reveal: two answer bubbles ("Bạn" / alias) or the reciprocal-hidden message; **Câu tiếp theo** → waiting state "Đang chờ {alias}…" until both ready. Completion: `ActivitySummary` with the revealed pairs, **Tiếp tục trò chuyện** (closes dock, focuses composer), `FeedbackChips`.

### 6.3 Quiz panel

"Vòng 2/5 · Đội: 4 điểm"; prompt; 4 option buttons; **Bỏ qua**. Waiting state as above. Reveal: options colored with icons + text (never color alone): correct ✓, each participant's choice labeled "Bạn"/alias; explanation line; round points "+3 (cả hai đúng!)". Summary: team score, per-round dots, list of questions with correct answers.

### 6.4 Focus panel

Before start: "Bắt đầu sau 5…" on both screens. Running: large countdown `mm:ss` (`aria-live="off"`; an `aria-live="polite"` line announces only phase changes and each 5-minute mark), phase label (Tập trung / Nghỉ), cycle "1/2", presence chips ("Bạn đang ở đây" / "{alias} đang ở đây | tạm rời"), controls **Tạm dừng** / **Tiếp tục**, **Rời phiên** / **Vào lại**, **Kết thúc** (confirmation). Collapsed: `FocusTimerChip` in the dock bar and chat header. Summary: factual minutes (self, peer, together), no badges.

### 6.5 Interruptions

- Peer blocks / ends / withdraws consent: dock closes, chat shows the existing closed notice; activity card reads "Hoạt động đã dừng vì kết nối không còn khả dụng".
- Stream drop: dock shows a subtle "Đang kết nối lại…" line; actions stay enabled (HTTP still works); state refreshes on reconnect.
- Reload mid-activity: dock reopens in the same round/phase from the server projection.
- 409 conflicts: refetch and show "Trạng thái vừa thay đổi, đã cập nhật" without losing a typed answer.

## 7. Loading, error, empty, offline

| State | Pattern |
|---|---|
| Loading | Skeletons for lists/cards; `role="status"` text for screen readers; buttons show "Đang …" text while busy |
| Error | `ErrorNotice` (existing) with **Thử lại**; typed text preserved |
| Empty | Honest copy + one primary next action |
| Offline | Global banner when `navigator.onLine === false`: "Mất kết nối mạng. Nội dung đang nhập vẫn được giữ." Writes are disabled with a tooltip; reads retry on `online` |
| Feature off | `StatePanel` explaining why (flag off, under 18, MATCH off, activities disabled) |

## 8. Accessibility requirements

- All new interactive elements reachable by keyboard; dock/sheet is a non-modal region (`role="region"`, labelled) on desktop and a modal dialog on mobile when expanded (focus trap, Escape collapses, focus returns).
- Tag pickers use native checkboxes; radios for single choice; error text linked via `aria-describedby`.
- Countdown does not spam screen readers (see 6.4). Reduced motion: no sheet spring animations, no pulsing dots.
- Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI boundaries; correctness indicated by icon + text.

## 9. Acceptance criteria by viewport

| Viewport | Criteria |
|---|---|
| 390 × 844 (mobile) | No horizontal scroll on Discovery (all tabs), Messages, Chat with dock expanded/collapsed; bottom nav hidden in chat; touch targets ≥ 44 × 44; candidate card actions visible without horizontal overflow; dock expanded leaves header visible |
| 390 × 480 (keyboard open) | Composer and newest message visible together; collapsed dock bar does not cover the composer; activity text field scrolls into view on focus |
| 430 × 932 | Same as 390; quiz options in one column; focus countdown ≥ 48 px font |
| 768 × 1024 (tablet) | Rail navigation; dock as bottom sheet; Discovery cards in 2 columns |
| 1280 × 900 / 1440 × 960 | Side-panel dock 380 px; chat log ≥ 480 px wide; Discovery cards 2–3 columns; no layout shift when dock opens |
| All | axe (`wcag2a`, `wcag2aa`, `wcag21aa`) 0 violations on: Discovery (3 tabs), Messages, Chat (no activity), Chat with each activity panel, Admin queue; reduced-motion run passes |

## 10. Visual evidence

H-04 captures screenshots for every screen in §9 via the full-stack harness into `docs/productization/screens/` (new) — never overwriting historical baselines in `docs/plans/validation-artifacts/visual/` (restore them if the harness rewrites them).
