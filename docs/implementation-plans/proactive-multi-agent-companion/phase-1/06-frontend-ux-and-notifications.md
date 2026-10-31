# Phase 1 — 06. Frontend UX và thông báo trong ứng dụng

Nguyên tắc: giữ ngôn ngữ thị giác hiện có ([DESIGN.md](../../../../DESIGN.md), [agent-chat.css](../../../../frontend/src/features/real/agent-chat.css)); bảng màu trắng/xám chỉ dùng trong màn chat AI, roster/sidebar giữ token hiện tại. Không thiết kế lại trang không liên quan. Không dùng các từ "cron", "handoff", "agent run", "context stamp", "SSE", "worker", "embedding" trên UI. Baseline trực quan: [92](../92-visual-qa-and-agent-browser.md).

## 1. Thuật ngữ hiển thị

| Khái niệm kỹ thuật | Chữ trên UI |
| --- | --- |
| Proactive message | **Lời hỏi thăm** |
| Schedule | **Lịch hỏi thăm** |
| Morning / evening slot | **Buổi sáng** / **Buổi tối** |
| Quiet hours | **Giờ yên lặng** |
| Unread | **Lời nhắn mới** / chấm báo |
| Journal context consent | **Dùng khoảnh khắc đã lưu hôm qua** |
| Paused | **Đang tạm dừng** |

## 2. Điểm vào

| Nơi | Thành phần | Hành vi |
| --- | --- | --- |
| Tài khoản (`/profile`) | Section mới "Lời hỏi thăm từ trợ lý" trong `AccountPage` ([RealApp.tsx:1969-1979](../../../../frontend/src/features/real/RealApp.tsx#L1969)) | Tóm tắt "2 lời hỏi thăm mỗi ngày" + nút "Chỉnh lịch hỏi thăm" → `/check-ins` |
| Thông tin cuộc trò chuyện | Section mới trong `InfoContent` ([ConversationInfo.tsx:197-249](../../../../frontend/src/features/real/ConversationInfo.tsx#L197)) | "Nhịp hỏi thăm bạn lúc 07:30 mỗi sáng." hoặc "Nhịp chưa hỏi thăm bạn." + link "Đổi lịch" → `/check-ins#nhip` |
| Dưới một lời hỏi thăm trong chat | Link nhỏ | "Đổi hoặc tắt lời hỏi thăm này" → `/check-ins#nhip` |
| Route mới | `/check-ins` (hash route, lazy như `JournalPage`) | Trang cài đặt (§3) |

## 3. Trang "Lịch hỏi thăm" (`/check-ins`)

### 3.1 Bố cục

```text
Desktop ≥1100px (cột đọc, giống trang Tài khoản)            Mobile 390px
┌──────────────────────────────────────────────┐           ┌──────────────────────────┐
│ Lời hỏi thăm từ trợ lý                        │           │ ← Lời hỏi thăm từ trợ lý  │
│ Trợ lý chỉ nhắn vào giờ bạn chọn. Bạn có thể  │           │ Trợ lý chỉ nhắn vào giờ   │
│ tắt bất cứ lúc nào. Tối đa 4 lời mỗi ngày.    │           │ bạn chọn…                 │
│ Đang dùng 2/4 · Múi giờ: Hà Nội (GMT+7) [Đổi] │           │ Đang dùng 2/4             │
├──────────────────────────────────────────────┤           ├──────────────────────────┤
│ (◉) Nhịp · Cảm xúc & thói quen                │           │ (◉) Nhịp                  │
│   Buổi sáng   [■ Bật]  07:30 ▾  Mỗi ngày ▾     │           │  Buổi sáng      [■ Bật]   │
│   Buổi tối    [□ Tắt]                          │           │  07:30 ▾ · Mỗi ngày ▾     │
│   ☑ Dùng khoảnh khắc đã lưu hôm qua           │           │  Buổi tối       [□ Tắt]   │
│     Nhịp chỉ đọc khoảnh khắc đã lưu của ngày   │           │  ☐ Dùng khoảnh khắc…      │
│     hôm qua để gợi ý một việc nhỏ. Không đọc   │           │  [Tạm dừng ▾] [Xóa lịch]  │
│     bản nháp, ảnh, âm thanh. [Tìm hiểu thêm]   │           ├──────────────────────────┤
│   [Tạm dừng ▾]  [Xóa lịch]                     │           │ (◉) Rủ Rê …               │
├──────────────────────────────────────────────┤           └──────────────────────────┘
│ (◉) Rủ Rê · Học hỏi & cùng chơi …              │
│ (◉) Mây … (◉) Gương …                          │
│ (◉) Cầu Nối · Tìm bạn đồng điệu                │
│   Cần bật tính năng kết nối để Cầu Nối hỏi thăm│
│   [Mở cài đặt kết nối]                          │
├──────────────────────────────────────────────┤
│ Giờ yên lặng  22:00 – 07:00  [Đổi]             │
│ ☑ Hiện chấm báo khi có lời nhắn mới            │
└──────────────────────────────────────────────┘
```

### 3.2 Thành phần và hành vi

| Thành phần | Chi tiết |
| --- | --- |
| Thẻ trợ lý | Avatar hiện có (`BotAvatar`), tên, vai trò; `section` có `aria-labelledby` tên trợ lý; anchor `#nhip` |
| Công tắc khung giờ | `<input type="checkbox" role="switch">` kèm nhãn "Buổi sáng" — trạng thái đọc "Bật"/"Tắt"; ≥44 px |
| Chọn giờ | `<select>` bước 15 phút trong khung hợp lệ (sáng 05:00–11:30, tối 17:00–22:30; teen tối ≤ 21:00) **trừ** các giờ nằm trong giờ yên lặng hiện tại (mặc định 22:00–07:00 ⇒ tối chỉ tới 21:45, sáng từ 07:00); dưới danh sách có gợi ý "Muốn chọn muộn hơn? Đổi giờ yên lặng". Dùng `select` thay vì `input type=time` để không cho chọn giờ sai và đọc tốt bằng screen reader |
| Lặp lại | `select`: Mỗi ngày / Ngày thường (T2–T6) / Cuối tuần / Tự chọn… → mở nhóm 7 checkbox "T2…CN" |
| Tạm dừng | Menu: "1 ngày", "3 ngày", "7 ngày" → `pausedUntil` = ngày cuối, hiển thị "Đang tạm dừng đến hết 03/11" + nút "Tiếp tục"; "Đến khi mình bật lại" → `enabled=false` nhưng **giữ** giờ và ngày lặp (bật lại khôi phục y nguyên) |
| Xóa lịch | `Dialog` xác nhận (component hiện có): "Xóa lịch hỏi thăm của Nhịp? Các lời hỏi thăm đã nhận vẫn còn trong cuộc trò chuyện." |
| Opt-in nhật ký (chỉ Nhịp) | Checkbox + mô tả + "Tìm hiểu thêm" mở `Dialog` giải thích (§9); mặc định **bỏ chọn** |
| Múi giờ | Hiển thị tên thân thiện + GMT. "Đổi" mở `Dialog`: lựa chọn "Dùng múi giờ của thiết bị (Hà Nội, GMT+7)" (lấy từ `Intl.DateTimeFormat().resolvedOptions().timeZone`) hoặc danh sách tìm kiếm; ghi chú "Ngày của nhật ký vẫn theo múi giờ tài khoản." |
| Giờ yên lặng | Hai `select` bắt đầu/kết thúc, khoảng 4–12 giờ |
| Lưu | Lưu **ngay khi đổi từng điều khiển** (optimistic có khóa từng thẻ), giống công tắc hệ thống; hiển thị "Đã lưu" (`role="status"`) cạnh thẻ; lỗi hiển thị trong thẻ |
| Lần giao kế tiếp | Dòng phụ: "Lần tới: 07:30 sáng mai" (từ `nextDeliveryAt`) |

### 3.3 Trạng thái

| Trạng thái | Nội dung |
| --- | --- |
| Đang tải | `p role="status"`: "Đang tải lịch hỏi thăm…" |
| Lỗi tải | `ErrorNotice` hiện có + "Thử lại" |
| Chưa bật gì | Khối giới thiệu: "Chưa có trợ lý nào hỏi thăm bạn. Bật buổi sáng hoặc buổi tối ở một trợ lý bạn thích." |
| Tính năng tắt (`available=false`) | `StatePanel`: "Lời hỏi thăm chưa mở cho tài khoản của bạn." |
| Guest | Không có điểm vào; route trả `GuestLocked` ("Tạo tài khoản để nhận lời hỏi thăm.") |
| Đã đạt 4/4 | Công tắc còn lại `aria-disabled="true"` + mô tả "Bạn đã dùng 4 lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này." |
| Auto-pause | Banner trong thẻ: "Mình tạm dừng lời hỏi thăm của Rủ Rê vì 3 lời gần đây bạn chưa mở. Bật lại khi bạn muốn nhé." + "Bật lại" |
| Cầu Nối không đủ điều kiện | Teen: "Cầu Nối chỉ dành cho tài khoản từ 18 tuổi." Adult chưa bật MATCH: "Cần bật tính năng kết nối…" + link |

## 4. Lời hỏi thăm trong cuộc trò chuyện

```text
                 ─────────── Hôm nay ───────────
  ☀ Lời hỏi thăm buổi sáng · 07:31
  Chào buổi sáng! Hôm qua bạn có ghi một khoảnh khắc thấy "hơi mệt" sau giờ học.
  Hôm nay thử đi bộ chậm 10 phút sau bữa trưa nhé — không cần làm hết.
  Bài viết đã tham khảo: 30/10/2026
  Đổi hoặc tắt lời hỏi thăm này
```

| Phần | Quy định |
| --- | --- |
| Nhãn | Dòng `metadata` (0,8125 rem, `chat-muted`) với icon `Sun`/`Moon` (lucide, `aria-hidden`): "Lời hỏi thăm buổi sáng · 07:31". Đọc cho screen reader: "Lời hỏi thăm buổi sáng từ Nhịp lúc 07:31" |
| Bubble | Như tin bot thường (không khung, không nền), nhóm theo [02 §9](02-multi-message-contract.md) |
| Nguồn | Dòng "Bài viết đã tham khảo" do backend tạo, giữ nguyên link `/self/entry/{id}` hiện có |
| Hành động phụ | Link "Đổi hoặc tắt lời hỏi thăm này" dưới nhóm (không phải nút lớn) |
| Không có nút "Trả lời nhanh" | Người dùng trả lời bằng composer như bình thường; starters không hiện lại |

## 5. Chỉ báo chưa đọc

| Vị trí | Hiển thị | Ghi chú a11y |
| --- | --- | --- |
| Tab "Trợ lý" trong `Navigation` ([RealApp.tsx:670-717](../../../../frontend/src/features/real/RealApp.tsx#L670)) | Badge số như "Tin nhắn" (`badgeText`, "9+") | `aria-label="Trợ lý, 2 lời nhắn mới"` theo mẫu hiện có |
| Mỗi dòng trợ lý trong roster | Chấm/số bên phải thay mũi tên khi có unread | Link đọc "Nhịp, AI, Cảm xúc & thói quen, 1 lời nhắn mới" |
| Đầu roster | Mục "Lời nhắn mới" (chỉ khi có): danh sách "Nhịp · Lời hỏi thăm buổi sáng · 07:31" (không preview nội dung) + "Đánh dấu đã đọc tất cả" | `section aria-labelledby`; mỗi mục là link tới `/assistants/nhip?conversation=…` |
| Lịch sử trò chuyện | Chấm nhỏ cạnh hội thoại có unread | — |
| Mobile full-chat | Thanh điều hướng bị ẩn trong chat; nút quay lại `←` hiển thị chấm khi trợ lý **khác** có lời nhắn mới | `aria-label="Về danh sách trợ lý, có 1 lời nhắn mới"` |

`badgesEnabled=false` → ẩn badge/chấm, vẫn giữ mục "Lời nhắn mới". Không có toast, âm thanh, rung, popup.

## 6. Đánh dấu đã đọc, polling, đồng bộ nhiều tab

- Hook mới `useAIInbox()` (đặt cạnh `useSocialSummary`, cùng mẫu: poll 30 s khi `document.visibilityState === "visible"`, refresh khi `focus`, giữ số cũ nếu lỗi).
- Đánh dấu đã đọc khi: hội thoại đang mở **và** tab visible **và** tin proactive đầu tiên nằm trong viewport ≥ 50 % (IntersectionObserver) hoặc người dùng ở cuối log. Gọi `PUT /ai/conversations/{id}/read` với `lastReadSequence = sequence lớn nhất đang hiển thị`; debounce 1 s.
- Khi `useAIInbox` thấy `latest.conversationId` trùng hội thoại đang mở và client **idle** (không gửi/không stream) → tải lại hội thoại (`GET`) để hiện lời hỏi thăm mới mà không cần reload.
- `BroadcastChannel("moodprint-ai-inbox")` (đã có tiền lệ `moodprint-guest`, [RealApp.tsx:254](../../../../frontend/src/features/real/RealApp.tsx#L254)): phát `{type:"read", conversationId, sequence}` và `{type:"refresh"}`; tab nhận cập nhật badge ngay. Không gửi nội dung tin.
- Back/forward: route và `?conversation=` đã do `HashRouter` quản lý; đánh dấu đọc chạy lại khi route mount.

## 7. Xung đột version khi có lời hỏi thăm mới

Hiện `send()` gửi `expectedConversationVersion` và lỗi `STALE_VERSION` chỉ hiển thị chung ([RealApp.tsx:1392-1404](../../../../frontend/src/features/real/RealApp.tsx#L1392)). Mới:

1. Nhận `409 STALE_VERSION` → **không** xóa draft; `GET` hội thoại; cập nhật danh sách tin.
2. Hiện `p role="status"`: "Có tin mới từ Nhịp. Tin của bạn vẫn còn trong ô nhập — gửi lại khi bạn sẵn sàng."
3. Giữ `clientMessageId` cũ cho lần gửi lại (server chưa chấp nhận lần trước nên không trùng).

## 8. Hiển thị nhiều bubble

- `ValidatedReply` từ stream v2 → chèn N tin vào state **một lần** (một cập nhật `update()`), id thật từ `messageId`.
- Render: gom tin liền kề cùng `runId` + `actor="bot"` thành `div.message-group`; khoảng cách trong nhóm `var(--space-2)` thay vì khoảng cách giữa các lượt; metadata (giờ + sao chép) ở bubble cuối, vẫn có ở từng bubble khi focus/chạm (giữ hành vi hiện có).
- Live region: vì cả nhóm được chèn một lần, `aria-live="polite"` đọc nhóm một lần. Nhãn nhóm: "Tin nhắn từ Nhịp, 2 phần".
- Sửa nhãn ngày: `messageDates.ts:23` đổi `"Today"`/`"Yesterday"` → `"Hôm nay"`/`"Hôm qua"` (lỗi baseline; lời hỏi thăm dựa nhiều vào nhãn ngày).

## 9. Giải thích quyền riêng tư (Dialog "Tìm hiểu thêm")

> **Nhịp dùng khoảnh khắc hôm qua như thế nào?**
> Mỗi sáng bạn đã hẹn, Nhịp đọc tối đa 3 khoảnh khắc **đã lưu** của ngày hôm qua (chữ, cảm xúc, yếu tố bạn chọn) để gợi ý một việc nhỏ cho hôm nay. Nhịp không đọc bản nháp, ảnh, âm thanh, video, và không chia sẻ với trợ lý khác hay với bạn kết nối. Nếu hôm qua bạn không viết gì, Nhịp chỉ chào bình thường. Bạn tắt lúc nào cũng được; khi tắt, Nhịp ngừng dùng ngay cả những lời gợi ý cũ trong cuộc trò chuyện. Lời hỏi thăm đã nhận vẫn nằm trong lịch sử trò chuyện cho tới khi cuộc trò chuyện hết hạn hoặc bạn xóa.

## 10. Thông điệp lỗi (tiếng Việt)

| Code | Thông điệp |
| --- | --- |
| `PROACTIVE_DAILY_CAP` | "Bạn đã dùng 4 lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này." |
| `SCHEDULE_WINDOW` | "Buổi sáng chọn từ 5:00 đến 11:30, buổi tối từ 17:00 đến 22:30." (teen: "…đến 21:00") |
| `SCHEDULE_IN_QUIET_HOURS` | "Giờ này nằm trong giờ yên lặng của bạn. Chọn giờ khác hoặc đổi giờ yên lặng." |
| `PROACTIVE_INELIGIBLE` | "Trợ lý này chưa thể hỏi thăm với tài khoản hiện tại." |
| `PROACTIVE_UNAVAILABLE` | "Lời hỏi thăm đang tạm nghỉ. Bạn thử lại sau nhé." |
| `STALE_VERSION` (lịch) | "Lịch vừa được thay đổi ở nơi khác. Mình đã tải lại để bạn xem." |

## 11. Accessibility

- Mọi điều khiển ≥ 44 px, nhãn hiển thị (không chỉ placeholder), nhóm bằng `fieldset/legend` cho "Lặp lại".
- Kết quả lưu thông báo qua `role="status"` cục bộ, không dùng `alert` trừ lỗi chặn.
- Focus: mở `/check-ins#nhip` → focus heading thẻ Nhịp (`useRouteFocus`/`focusRouteHeading` hiện có).
- Không dùng màu làm tín hiệu duy nhất: badge có số, chấm có nhãn ẩn.
- Tương phản: dùng `--color-muted` hiện có (đã đạt AA trên nền trắng theo DESIGN.md).

## 12. Responsive

| Breakpoint | Trang lịch | Chat |
| --- | --- | --- |
| ≥ 1100 px | Cột đọc giữa, thẻ 2 cột điều khiển (nhãn trái, điều khiển phải) | Roster + chat; mục "Lời nhắn mới" trên roster |
| 768–1099 px | Một cột, điều khiển xếp dưới nhãn | Như hiện tại (rail + chat) |
| < 768 px | Một cột, nút quay lại; menu tạm dừng mở dạng sheet (`Dialog`) | Full-chat ẩn tab bar; chấm trên nút quay lại |

## 13. Motion

Dùng `useGSAP` + `gsap.matchMedia("(prefers-reduced-motion: no-preference)")` như [ConversationInfo.tsx:82-95](../../../../frontend/src/features/real/ConversationInfo.tsx#L82). Chỉ: (a) entrance nhóm bubble ([02 §9](02-multi-message-contract.md)); (b) badge xuất hiện scale 0.9→1 trong 100 ms. Không animate khi tải lịch sử, không pulse lặp, không confetti.

## 14. Tài liệu UI cần cập nhật khi triển khai

[docs/frontend/ui-accessibility.md](../../../frontend/ui-accessibility.md), [docs/frontend/data-flow.md](../../../frontend/data-flow.md), và DESIGN.md (thêm mục "Proactive greeting label" và "Message group") sau khi build xong, theo quy trình `impeccable` hiện có của dự án.
