# Test thay đổi trong journal intelligence

Inventory theo diff source, không phải số ca runtime (template/width được Playwright mở rộng). Baseline source là `e2c3e5e8`. Các mục “tên cũ” có thể được viết lại dưới tên mới; bảng không coi mọi đổi tên là mất coverage. Không thêm skip/xfail. Kết quả thực thi nằm trong [ledger](08-execution-ledger.md).

## Browser: test bị gỡ hoặc đổi tên

| File | Tên cũ | Lý do |
| --- | --- | --- |
| `frontend/tests/e2e/activities.spec.ts` | "opening the activity dialog keeps text opaque throughout its entrance" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "an invitee accepts, answers, waits, then sees both answers revealed" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a skipper sees the reciprocal-hidden message" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "quiz reveal marks the correct answer and choices with text, not colour alone" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "focus countdown follows server time, not the device clock" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a decline cooldown disables only that invitation kind" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "contact details in a message prompt a non-blocking advisory" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "on a phone the dock is a sheet above the composer that collapses and keeps the draft" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "on a desktop the dock is a side panel next to the log" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "finished activities appear in the log where they ended" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a pending refresh cannot reopen a dismissed summary and a new invitation still appears" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a failed catalog read keeps the entry and offers a retry inside the dialog" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a failed first invitation stays visible in the dialog and retrying keeps the plan and intent" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "a focus invitation names the exact plan and offers a real decline" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "the dock enters with at most 16px of travel and fully readable text" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/activities.spec.ts` | "with reduced motion the dock appears in place" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/e2e/auth.spec.ts` | "identity values typed while the stored value loads are never overwritten" | Gỡ identity editor thuộc hồ sơ social; giữ các test đăng nhập, recovery, phiên và xóa tài khoản. |
| `frontend/tests/e2e/auth.spec.ts` | "the gender selector normalizes a stored value and saves the chosen canonical value only on request" | Gỡ identity editor thuộc hồ sơ social; giữ các test đăng nhập, recovery, phiên và xóa tài khoản. |
| `frontend/tests/e2e/discovery.spec.ts` | `T13 T17 T32: complete deliberate publication by touch at ${width}px` | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T19: session expiry clears a dirty editor and ignores a delayed save response" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T12 T14 T19: refresh failure keeps the mounted dirty reducer and exit confirmation" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T14 T19: terminal eligibility refusal clears publication and preserves secure exit" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T12 T14: a CSRF refusal retains edits and an accessible exit guard" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T33: consecutive featured removals retain next, previous and final heading focus" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T06 T33: picker tray removal keeps keyboard focus and Escape restores its launcher" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T08 T33: full-interest deletion retains consecutive and final action focus and announces removal" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T32 T33 T34 T35 T37: concise announcements, errors, forced colors, 200% text and targets" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T18: reconcile an uncertain save through GET without repeating the write" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T18: uncertain publication reconciles the exact live snapshot without auto retry" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T27 T28: sent status stays, skip focuses next peer and expired ref never replays" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T11 T12 T14 T18: private partial save, same-intent retry and explicit conflict overwrite" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T14 T15: Forward, repeated Back, shell route, discard and native reload warning" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T11 T13 T17 T36: missing public facets stay explicit; preview then final consent click" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T05 T06 T32 T33 T34 T35: mobile preview, concrete picker, reflow and keyboard" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T24 T25 T26: peer alias, factual reasons and grounded starter stay public-only" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T01 T03 T04 T10: three questions, eight entries and immediate local preview" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T14 T15: dirty Back/cancel/save/Forward retains native history state" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "T07 T12 T13 T16: legacy full data, failed save, exact reviewed snapshot and separate publish" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "discovery tabs follow the arrow keys and keep the tab in the URL" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "pending invitations badge the nav and the tab, and the nav opens them" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "the main navigation opens the profile editor for adults without a live profile" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "the main navigation opens suggestions for a live profile" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/discovery.spec.ts` | "minors reach the global age gate without loading candidates" | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/e2e/guest.spec.ts` | "people-matching and messaging are explained without any social request" | Boundary đăng ký chuyển sang check-in; giữ không request social và các ca hủy/unknown outcome/phiên guest. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR01: a starter fills an empty draft and sends nothing" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR01: a starter is inserted at the caret and keeps the existing draft" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR01: a starter replaces only the selected range" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR01: an insertion past 500 characters keeps the draft and says so" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR01: the contact-information advisory still guards a draft built from a starter" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR02: an edit made while a human-chat POST is pending survives its receipt" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR02: an unedited human-chat draft is cleared by its receipt" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR09: a committed-but-lost response is reported as unconfirmed, keeps the plan, and the retry creates one invitation" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR09: a dropped connection is also unconfirmed, not a definite failure" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR09: a refusal keeps the server's own explanation" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR10: only the invitation being sent says it is sending" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/merge-readiness.spec.ts` | "MR11: every tab in the discovery tablist points at a panel that exists" | Gỡ starter/receipt human chat, invitation và discovery tab; giữ các race/draft/cancel/recovery AI. |
| `frontend/tests/e2e/social.spec.ts` | "matching publishes the reviewed profile only after a committed receipt" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "candidate cards show a qualitative label and at most three reasons, never a percentage" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "an incoming request shows the sender's public card before accepting" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "navigation badges, unread rows and the private read marker" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "a refused publish keeps the reviewed choices and never claims the profile is shown" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "closing the editor with unsaved choices asks before discarding them" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "with MATCH withdrawn the profile tab says showing a reviewed profile is the way back" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/social.spec.ts` | "sending an invitation is named as an invitation, with a matching receipt" | Gỡ màn chat và kết nối người với người; không xóa router/backend tests. |
| `frontend/tests/e2e/states.spec.ts` | "with activities switched off the chat has no activity entry" | Trạng thái loading/error/empty/offline chuyển sang AI/roster; bổ sung guard gửi AI khi offline. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "with MATCH withdrawn, messages lead to reviewing and showing the matching profile" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "the chat block dialog states in-app irreversibility, focuses cancel and sends nothing on cancel" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "five primary destinations, with Nhật ký opening the mood journal directly" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "human chat keeps the application palette after visiting the redesigned AI chat" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "a peer message arriving while reading older messages keeps the place and is not marked read" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "safety actions open from the conversation header and stay away from Send" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/fullstack/activities.spec.ts` | "an icebreaker keeps answers private until both answer and resumes after a reload" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/fullstack/activities.spec.ts` | "a cooperative quiz hides the answer until both choose and scores as a team" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/fullstack/activities.spec.ts` | "a one-cycle shared focus session runs on server time to completion" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/fullstack/activities.spec.ts` | "either participant can explicitly stop focus and both reload the same summary" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/fullstack/activities.spec.ts` | "blocking mid-activity closes the peer's dock and the room" | Gỡ UI lời mời/quiz/focus hai người; backend activities vẫn được kiểm thử. |
| `frontend/tests/fullstack/journeys.spec.ts` | "real FastAPI/PostgreSQL preserves mood, streams through the SDK, and connects two users" | Journey hỗn hợp giữ mood/SDK/accessibility; bỏ reveal/kết nối/report qua social UI đã gỡ. |
| `frontend/tests/fullstack/journeys.spec.ts` | "only the identity owner grants reveal, revocation removes access, and reporting is separate from blocking" | Journey hỗn hợp giữ mood/SDK/accessibility; bỏ reveal/kết nối/report qua social UI đã gỡ. |
| `frontend/tests/fullstack/matching-v2.spec.ts` | `T10 T11 T13 T17 T19: real private draft reload and explicit publication (${scorer})` | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/fullstack/matching-v2.spec.ts` | `T07 T17 T20 T22: metadata survives older writers with full public data (${scorer})` | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/fullstack/matching-v2.spec.ts` | `matching (${scorer}) ranks real profiles with qualitative labels and honest rules` | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/fullstack/matching-v2.spec.ts` | `a profile with a v2-only goal still receives suggestions (${scorer})` | Gỡ UI matching/public profile; giữ các test matching backend. |
| `frontend/tests/fullstack/moderation.spec.ts` | "a report reaches the staff queue and a restriction removes the subject from discovery" | Viết lại qua report seed chỉ test, vẫn giữ queue → restriction và server authorization. |
| `frontend/tests/fullstack/mvp.spec.ts` | "Journey B/C: two users match, request, accept and chat; stale tab loses access on MATCH withdrawal; C is denied" | Gỡ phần match/human chat; responsive và axe chuyển sang mood/AI/nhật ký/tài khoản. |
| `frontend/tests/fullstack/mvp.spec.ts` | "Journey D: block keeps report-after-block possible, the peer's tab closes, and ending needs confirmation" | Gỡ phần match/human chat; responsive và axe chuyển sang mood/AI/nhật ký/tài khoản. |
| `frontend/tests/fullstack/mvp.spec.ts` | "Journey F: mood, matching and chat stay usable at 390px and 430px with the composer in view" | Gỡ phần match/human chat; responsive và axe chuyển sang mood/AI/nhật ký/tài khoản. |
| `frontend/tests/fullstack/product-experience.spec.ts` | "all five assistants explain their purpose and link to the related real feature" | Bỏ starter gửi sang peer và related tool social; giữ hướng dẫn trợ lý/các công cụ cá nhân. |
| `frontend/tests/fullstack/product-experience.spec.ts` | "a conversation starter stays editable and reaches the other account only after Send" | Bỏ starter gửi sang peer và related tool social; giữ hướng dẫn trợ lý/các công cụ cá nhân. |
| `frontend/tests/fullstack/responsive.spec.ts` | "social screens are responsive and pass axe at every acceptance size" | Viết lại cùng matrix kích thước/axe cho AI, nhật ký, tài khoản và admin còn tồn tại. |

## Browser: test giữ tên nhưng viết lại body

| File | Test | Lý do |
| --- | --- | --- |
| `frontend/tests/e2e/eligibility.spec.ts` | `ineligible account keeps secure account controls and accessible layout at ${width}px` | Cập nhật nav/copy/fixture bỏ social, giữ hành vi và assertion ngoài phạm vi. |
| `frontend/tests/e2e/guest.spec.ts` | `end and register opens signup after one confirmation at ${width}px` | Boundary đăng ký chuyển sang check-in; giữ không request social và các ca hủy/unknown outcome/phiên guest. |
| `frontend/tests/e2e/guest.spec.ts` | "end and register cancellation keeps the private view and restores focus" | Boundary đăng ký chuyển sang check-in; giữ không request social và các ca hủy/unknown outcome/phiên guest. |
| `frontend/tests/e2e/guest.spec.ts` | `end and register ${failureKind} failure stays honest and retryable` | Boundary đăng ký chuyển sang check-in; giữ không request social và các ca hủy/unknown outcome/phiên guest. |
| `frontend/tests/e2e/motion.spec.ts` | "route changes swap content immediately without fading it in" | Cập nhật nav/copy/fixture bỏ social, giữ hành vi và assertion ngoài phạm vi. |
| `frontend/tests/e2e/proactive.spec.ts` | `check-in schedule page is usable and accessible at ${width}px` | Cập nhật nav/copy/fixture bỏ social, giữ hành vi và assertion ngoài phạm vi. |
| `frontend/tests/e2e/real.spec.ts` | "validated AI cards navigate to existing tools without claiming a saved action" | Cập nhật nav/copy/fixture bỏ social, giữ hành vi và assertion ngoài phạm vi. |
| `frontend/tests/e2e/states.spec.ts` | "offline shows one banner, disables sending and keeps the draft" | Trạng thái loading/error/empty/offline chuyển sang AI/roster; bổ sung guard gửi AI khi offline. |
| `frontend/tests/e2e/states.spec.ts` | "a failed list shows retry, and coming back online retries by itself" | Trạng thái loading/error/empty/offline chuyển sang AI/roster; bổ sung guard gửi AI khi offline. |
| `frontend/tests/e2e/states.spec.ts` | "loading lists announce themselves" | Trạng thái loading/error/empty/offline chuyển sang AI/roster; bổ sung guard gửi AI khi offline. |
| `frontend/tests/e2e/states.spec.ts` | "empty screens say so honestly and offer one next step" | Trạng thái loading/error/empty/offline chuyển sang AI/roster; bổ sung guard gửi AI khi offline. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "navigation labels are readable and ordinary targets are at least 44px" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | `redesigned screens have no automated WCAG violations at ${width}px` | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/e2e/ux-redesign.spec.ts` | "the skip link stays hidden until focused, then appears and moves focus to main" | Bỏ human chat/discovery/block UI; nav đổi 5→3, giữ AI draft/focus/reflow/axe. |
| `frontend/tests/fullstack/guest-journey.spec.ts` | "end and register opens signup after one confirmed HTTP end" | Boundary đăng ký chuyển sang check-in; giữ không request social và các ca hủy/unknown outcome/phiên guest. |
| `frontend/tests/fullstack/journeys.spec.ts` | "real authenticated screens reflow and pass automated accessibility checks at mobile and desktop sizes" | Journey hỗn hợp giữ mood/SDK/accessibility; bỏ reveal/kết nối/report qua social UI đã gỡ. |
| `frontend/tests/fullstack/mvp.spec.ts` | "Every real screen passes axe and reflows at 1440, 1280, 430 and 390 with reduced motion" | Gỡ phần match/human chat; responsive và axe chuyển sang mood/AI/nhật ký/tài khoản. |
| `frontend/tests/fullstack/product-experience.spec.ts` | "document branding and short pages stay at the top across all six sizes" | Bỏ starter gửi sang peer và related tool social; giữ hướng dẫn trợ lý/các công cụ cá nhân. |

## Unit frontend bị gỡ cùng module

| File | Test | Lý do |
| --- | --- | --- |
| `frontend/src/features/real/activities/activityView.test.ts` | "knows whose turn it is" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/activityView.test.ts` | "explains what we are waiting for" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/activityView.test.ts` | "summarizes progress for the collapsed bar" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/activityView.test.ts` | "allows an invite only without an open session or a decline cooldown" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/activityView.test.ts` | "describes endings relative to the viewer" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/clock.test.ts` | "follows the server when it is ahead of the device" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/clock.test.ts` | "follows the server when it is behind and never goes below zero" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/activities/clock.test.ts` | "formats minutes and seconds" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/conversationStarters.test.ts` | "requires the exact server reason and the peer interest" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/conversationStarters.test.ts` | "keeps priority independent of reason ordering and ignores expiring reference" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/conversationStarters.test.ts` | "reaches both safe variants from public seeds and versions" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "projects only featured interests; opening legacy profile is clean and preserves all facets" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "follows intention only before first save or explicit canonical override" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "rejects a fourth feature and retains focus-independent data and order" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "de-features tentative additions but keeps saved interests; explicit delete removes both" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "never replaces a retained interest at full max" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "requires new questions and canonical minimums, never inventing values/languages" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "invalidates a server review on edits while preserving style/activity" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "blocks incompatible taxonomy instead of dropping unknown saved fields" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "saving no featured interests does not silently re-feature retained data" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/discoveryProfile.test.ts` | "a failed draft save keeps the builder rather than bypassing the required questions" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/format.test.ts` | "describes recent times relatively and old ones by date" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/format.test.ts` | "prefixes own previews and explains an empty conversation" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/format.test.ts` | "caps badge numbers at 9+" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/pii.test.ts` | "flags %s" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/pii.test.ts` | "does not flag %s" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/profileRules.test.ts` | "requires three interests before continuing" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/profileRules.test.ts` | "checks values, languages and the optional facets per step" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/profileRules.test.ts` | "counts towards minimums and caps selections at the maximum" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |
| `frontend/src/features/real/social/profileRules.test.ts` | "falls back to the documented limits when the taxonomy has none" | Hàm thuần chỉ phục vụ component social/activity đã gỡ, không có consumer còn lại. |

## Backend: assertion/test cập nhật

- JI-31 sáu test `test_embeddings.py` đổi kết quả `list[str]` thành `MemoryText(text, 'approved')`: tenant/bot isolation, no opt-in/revocation fallback, config dimension fallback, Vietnamese semantic ranking, unrelated-data-version và no external query. Bảy assertion giá trị cập nhật đúng interface mới, giữ nguyên expected text, provider call counts và mọi authorization/bounds assertion.
- JI-31 guest operation inventory thêm `DELETE /memories/auto` vào registered-only; các ca guest 403/expired 401 tự mở rộng từ parametrization, không bỏ gate cũ.
- JI-31 `test_guest_review_regressions.py`: ba parameter của funded-admission guard và một ca funded-query replay đổi expected memory thành `MemoryText(text, 'approved')`; giữ zero external call khi flag/price/budget đóng, một query charge duy nhất và document-slot/usage assertions.

- JI-40 `test_registry_is_closed_and_loads_trusted_offline_workflows` đổi tên thành `test_registry_loads_six_trusted_skills`, equality đóng đổi 2→6 ID đúng đặc tả; các assertion metadata/path-security cũ giữ nguyên.
- JI-40 `test_guest_prompt_capabilities_are_a_zero_projection`: equality 2→6 skill; assertion tất cả skill/tool unavailable cho guest giữ nguyên.
- JI-40 test weekly dùng output JSON thực của tool và citation đã publish; evidence terminal phải được scrub theo privacy invariant, không sửa production cleanup.
- Hai locator menu trong `agent-skills.spec.ts` đổi theo menu sáu skill; giữ kiểm tra one-turn, retry cùng ID/options, keyboard focus và overflow ở cả bốn viewport.
- JI-31 một locator region trong `ux-redesign.spec.ts` đổi “Đã duyệt”→“Ghi nhớ đã lưu” vì section chứa cả memory approved và tự động; giữ kiểm tra pending proposal “Chưa lưu”, tách mục bị từ chối và nội dung memory đã lưu.

- `test_upgrade_from_0015_preserves_registered_rows_and_matches_models`: expected head 0028→0029; giữ bảo toàn registered rows, session lifetime, private grants và Alembic drift.
- `test_journal_upgrade_downgrade_preserves_legacy_mood_and_private_acl`: tháo/phục hồi migration phụ thuộc 0029 quanh diễn tập 0019 để không vi phạm FK mới; giữ nguyên mọi assertion và rollback temporary roles.
- Standalone chat/social load server: dùng `ALL_FEATURES_OFF` trước các override rõ ràng, thêm hai ca kiểm cấu hình subprocess không chạy server/provider.

- `test_guest_input_and_settings_defaults_fail_closed`: defaults bật nên kiểm configuration_missing và guest paid/feedback đóng khi thiếu config.
- `test_local_live_actor_allowlist_is_closed_by_default_and_rejected_in_production`: ghim ai_enabled=false để giữ phạm vi allowlist.
- `test_three_agents` legacy baseline: chỉ đổi tên mô tả, không đổi assertion.
- Production settings: thiếu provider key chuyển từ raise sang degraded; các assert auth/HTTPS/database/captcha giữ nguyên.
- Readiness: revision 0028 không đủ cho ORM mới, head bắt buộc 0029.
- `test_foundation.py`: assertion READY_REVISIONS dùng 0029; ca 0028 đổi 200→503, thêm ca 0029→200, giữ mọi revision cũ/unknown bị từ chối.
- `test_0020_preserves_journal_auth_matching_and_approved_memories`: constant HEAD đổi 0028→0029 để chạy hết chain hiện hành; giữ nguyên mọi assertion dữ liệu/RLS/rollback.
- `test_guest_aware_rollback_cannot_resurrect`: expected readiness head đổi 0028→0029; giữ denial, purge và peer-session assertions.
- `test_inventory_classifies_every_orm_table`: đăng ký route-owned models bằng app build offline trước assertion để chạy riêng không phụ thuộc side effect collection; không đổi equality hoặc danh sách nhóm lifecycle.
- `test_guest_permissions.py`: thêm GET/PUT journal/ai-settings vào registered-only; equality operation inventory không đổi, đồng thời thêm hai ca live guest 403/expired guest 401 qua parametrization có sẵn.
- `test_journal_query_cannot_choose_owner_drafts_or_unbounded_inputs`: invalid limit 6→9 theo giới hạn mới 8; giữ các payload owner/draft/date/query sai.
- `test_journal_search_is_owner_saved_date_and_size_bounded`: thêm field match; literal `100_` được recent fallback 2 bài, kiểm cả hai không giả thành keyword match. Owner/draft/window/size vẫn giữ.
- Hai test seed derivative trong `test_journal_ai_settings.py`: xóa job auto-enqueue của đúng entry synthetic trước fixture seed để tránh unique conflict; assertions không đổi.
- Version hangout 1→2: body không còn lời mời social.
