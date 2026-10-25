# 06 — Tích hợp frontend theo từng hành trình

> **Kiến trúc đã chốt ngày 23/10/2026:** Python 3.12/FastAPI/Pydantic v2, SQLAlchemy 2 async + psycopg 3, Alembic/uv, Supabase PostgreSQL/Auth và OpenAI Agents SDK Python. Giữ React/Vite/TypeScript; Pydantic → OpenAPI → `frontend/src/api/generated/`. Chỉ scaffold cloud, không deploy. Evidence audit ban đầu là lịch sử, không phải trạng thái implementation mới.

**Giữ UI hiện có, thay nguồn dữ liệu và quyền quyết định theo từng vertical slice.** Các file trong bảng là source hiện hữu; `features/*`, API hooks và SessionGate là file dự kiến, là target paths; trạng thái thực tế ghi trong implementation evidence. Không đổi router/design system hoặc xóa animation để làm tích hợp dễ hơn.

## Dữ liệu và state sau tích hợp

**Onboarding chốt 24/10/2026 (D15/Q04):** sau đăng nhập, tài khoản unknown nhập năm sinh và xác nhận đã đủ16 tuổi, chờ `PUT /users/me/eligibility` trả SessionView mới rồi mới mở shell. Dưới16 vẫn bị chặn. Tuổi16–17 chỉ dùng tính năng cá nhân; Tìm bạn/human chat/reveal cần18. Với người đang ở năm tròn18, checkbox18 là tùy chọn khi onboarding; chưa xác nhận vẫn dùng app, có thể xác nhận sau trong Settings. Không bật consent tự động; lỗi API giữ draft; năm sinh không vào published profile hoặc model context.

`App` tiếp tục dùng HashRouter. Thay `Provider → demoState` ở real entry bằng bootstrap `GET /api/v1/session`, server-state providers và các feature hooks. Local UI state giữ search, draft, modal, focus/scroll; server state gồm consent/profile/mood/memory/conversations/requests/rooms. Không thêm userId/role vào request theo giá trị từ reducer.

**D06:** thêm một server-state library có query keys rõ, đề xuất TanStack Query cho cache/invalidation/mutations; đây là dependency mới cần pin/compatibility check ở P01.04, không coi đã có. Nếu spike cho thấy native feature hooks đủ đơn giản, có thể dùng chúng nhưng phải đáp ứng cùng contract/error/cache tests và ghi decision. Không dùng cả hai cách rời rạc cho cùng resource. Streaming delta/replay có adapter riêng, không nhét mỗi token vào Context toàn app.

Query keys bắt đầu bằng auth session generation và resource ID; logout/session expired/revoke xóa queries nhạy cảm, đóng stream/socket, hủy mutations và không phục hồi cache từ localStorage. `Cache-Control:no-store` cho API riêng; app cache private chỉ RAM, có invalidation versions. Không thêm service worker/offline transcript persistence.

HTTP client chung tại `frontend/src/api/{client,errors}.ts`, types/client generated tại `frontend/src/api/generated/` từ FastAPI OpenAPI: credentials đúng site, CSRF header cho write, timeout/abort, typed DTO/ApiError Pydantic→OpenAPI, không viết schema chuẩn thứ hai [05](05-backend-data-realtime-plan.md). 401 đưa về SessionGate, 403 giải thích purpose gate, 409 yêu cầu tải lại/preview mới, 410 kết thúc phiên/proposal, 429 giữ draft và Retry-After, 503 giữ dữ liệu nhập và lối retry có chủ ý. Không retry write bằng clientMessageId/idempotency key mới.

## Mapping màn hình → feature → API/data/state

| Source/route có thật                                                                       | Feature thực cần nối                     | API/data chuẩn                                                | State còn thiếu và đường tích hợp                                                                                   |
| ------------------------------------------------------------------------------------------ | ---------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| [App.tsx](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/App.tsx#L31), mọi ScreenGate                                  | Auth/session/eligibility/consent         | `/session`, `/consents/:purpose`; flags/version server        | Loading bootstrap, đăng nhập, session hết hạn, under16/unknown fail-closed; giữ 4-tab shell sau gate                |
| [CompanionsPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/Companions.tsx#L30), `/assistants`          | Public roster + conversation previews    | `/bots`, own current SessionView per bot                      | Metadata lỗi/loading; preview không leak khi AI tắt/hết TTL; giữ search/avatar/unread                               |
| [BotConversation](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/Companions.tsx#L172), `/assistants/:botId` | AI run/thread/stream                     | Create conversation, send, SSE, cancel, SessionView           | Accepted/running/reconnect/partial/failed/expired; bind runId→thread, không rely turn parity                        |
| [InlineCardView](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/Cards.tsx#L68)                              | Typed cards/action receipts              | Tool proposals + confirm/reject; mood save; navigate actions  | Proposed/pending/succeeded/denied/expired; không tự hiển thị saved từ model text                                    |
| [SelfPage/MoodPage/Week](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Self.tsx#L19), `/self`                   | Mood CRUD và summary                     | `/moods/:date`, `/moods/summary`, sourceVersions              | Save pending/error/conflict, real date/timezone, loading/empty/null; manual path độc lập AI                         |
| [PrivateProfile](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Profile.tsx#L68), `/profile?tab=private`         | Private items + approved memories        | Private CRUD/proposal confirms, `/memories`                   | Owner list, pending/failed edit/delete, per-item memory scope/version; không xóa draft khi server reject            |
| [Sharing/Preview](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Profile.tsx#L304), `/profile?tab=sharing`       | Draft/preview/publish/withdraw           | matching-draft + published snapshots/previewDigest            | Draft saving/conflict, preview stale, publish pending, revoke invalidation; taxonomy public versioned/generated DTO |
| [ConnectPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Connect.tsx#L29), `/connect?tab=discover`           | Discovery và reasons                     | `/matching/candidates`, skips, blocks                         | Thay 400ms timer bằng query thật; skeleton/error/empty; bỏ bio/tagline hardcode khỏi real cards                     |
| [Requests](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Connect.tsx#L303), requests tab                        | Invitations và mutual state              | `/connection-requests`, accept/decline/cancel, `/connections` | Direction theo actor thật, stale/expired/quota; bỏ toàn bộ peer simulation real mode                                |
| [MessagesPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/App.tsx#L397), `/messages`                               | Room summaries/unread/last seq           | `/connections` + ID-only socket notifications                 | Loading/offline/revoked room; chỉ hiển thị preview khi còn quyền                                                    |
| [ChatPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Chat.tsx#L26), `/chat/:id`                             | Human chat, ACK/replay, safety           | Messages HTTP, room policy/version, socket notify             | Pending bubble/ACK/fail/retry, reconnect/gap/room revoked; peer là user thật, không `HUMAN_FINISH`                  |
| Chat reveal/options                                                                        | Reveal request/grant, end/block          | Reveal endpoints + no-store value endpoint                    | Owner-preview riêng, expired/conflict/denied, live revoke; không render peer identity trước grant                   |
| [Settings/Privacy](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Settings.tsx#L47), `/settings`                 | Consent, account identity, delete/export | consents, own identity, data-deletions, exports               | Switch pending/rollback, actual delete job status, reauth, truthful copy                                            |
| [Safety](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Settings.tsx#L201), settings safety                      | Block list/report receipt                | blocks, reports/selected evidence                             | Receipt thật sau commit; không nói “nhân viên đã nhận” nếu chưa có staffing                                         |
| Chat ActivityPanel/Concepts                                                                | ACT01 fixture/Future                     | Không nối production Activities trong baseline                | Giữ fixtures/tests; product entry ẩn hoặc unavailable theo Q01, không mô phỏng peer thật                            |

Login/eligibility gate, recorder, moderator workflow và trang quản lý memory riêng nếu cần là **bổ sung mới**, không phải màn hình đã tồn tại. Tận dụng Dialog/Settings/PrivateProfile trước khi tạo navigation mới. UI copy sản phẩm không nhắc “SQL transaction/SDK/session-store” trừ khi giúp user hiểu quyết định về dữ liệu.

## Hành trình 1 — Năm AI Companions

Điểm bắt đầu: tab **Trợ lý**, roster có đúng Mây/Gương/Nhịp/Rủ Rê/Cầu Nối. Search/starter prompts/avatars, responsive two-pane desktop và full-height mobile giữ nguyên.

| Bot / thao tác user                                             | Prototype trả gì và mock ở đâu                                        | Production cần nối / trạng thái / kiểm thử giữ trải nghiệm                                                                 |
| --------------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Mây: “Hôm nay mình hơi mệt” → “Kể một chút” → “Ghi lại cảm xúc” | Script parity/regex, 650ms timer; handoff card sang Nhịp              | Mây model thật, progress/cancel/retry; CTA mở Nhịp thread riêng không transcript; T-AI-01/04                               |
| Gương: nói sở thích → làm rõ → sửa/lưu/bỏ qua card              | Script tạo nhận xét, `AI_BOT_CARD` lưu RAM private nhưng không memory | Proposal server ephemeral; pending, edited confirmation, expired; private saved chỉ sau receipt; T-MEM-01/02               |
| Nhịp: chọn mood card → “Xem xu hướng”                           | Reducer lưu mood tự chọn; moodSummary tính từ fixture/self entries    | API save value/date/note thật; read summary có source; không suy mood từ lời tâm sự; T-MOOD-01/02                          |
| Rủ Rê: “Giải đố/Học gì đó” → xem đáp án/ví dụ                   | Câu đố/serendipity hardcode, card revealed trong RAM                  | Thư viện nội dung versioned, read tool/card; hoạt động cá nhân ngắn không đồng nghĩa Shared Activities production; T-AI-02 |
| Cầu Nối: chọn mục tiêu → xem gợi ý/sửa hồ sơ                    | Script/Link, không thật sự đổi profile hoặc gửi invite                | Draft proposal/taxonomy; user tự chọn, preview/publish ở domain flow; không nạp peer profiles vào model; T-MATCH-01        |

Lúc send: tạo clientMessageId và optimistic user bubble trạng thái accepted/pending; server 202 bind runId/conversationId/botId, giữ mapping ngay cả user đổi route. Progress có meaning (“Đang lấy số liệu”, “Đang chuẩn bị phản hồi”), không hiện chain-of-thought. Final chỉ reconcile theo messageId; duplicate events không thêm bubble. Retry giữ userMessageId của ý định cũ khi tra kết quả; run mới sau fail cần thông báo, không im lặng gọi lại model.

AI consent off: giữ hướng dẫn đi `/settings`, mood thủ công và tìm bạn như prototype; không tự bật AI để render card. Stop hủy đúng run của bot gốc. Reconnect spinner khác model-running; hết TTL báo kết thúc phiên và nút bắt đầu mới, không trưng ra history rỗng như thể chưa từng có lỗi.

Chế độ buffer [04](04-agents-sdk-architecture.md) vẫn có SSE progress và final; không làm typing delay giả 650ms. Nếu thử progressive text sau này, render plain text/sanitized markdown, delta batch theo frame hoặc khoảng 50ms, không animate lại tất cả tin mỗi token; screen reader thông báo theo message/progress, tránh aria-live đọc từng token. Giữ “Về tin mới nhất” và không kéo scroll khi user đang đọc phía trên.

## Hành trình 2 — Self-Discovery, mood, private và memory

Điểm bắt đầu hiện hữu: Nhịp card hoặc Tôi→biểu đồ→chi tiết, `/self?tab=mood|week`, `/profile?tab=private`. User tự chọn mood/note, lưu/sửa/xóa; hiện reducer cập nhật RAM và UI clear form ngay. Integration phải chờ thành công hoặc giữ nháp/retry khi lỗi. Sửa dùng expectedVersion, 409 không tự overwrite; delete có confirmation và trạng thái pending.

Ngày hiển thị dùng `Intl.DateTimeFormat` theo timezone trong session, bỏ `/10`; bucket ngày từ server, ngày thiếu=null, lựa chọn cuối trong ngày theo rule đã chốt. <3 ngày vẫn thấy số liệu tự ghi, chưa diễn giải xu hướng. Note/mood không xuất vào matching DTO. AI tắt vẫn CRUD và xem bảng/biểu đồ được.

PrivateProfile giữ kiểu item list, origin/status, “Đúng với mình/Không đúng/Sửa/Xóa”. Origin AI vẫn là lời gợi ý cần xác nhận, không biến thành nhãn tâm lý chắc chắn. Bổ sung rõ scope memory theo bot và mục “Cho phép dùng lại” riêng; tắt quyền không làm biến mất khả năng xem/sửa/xóa dữ liệu của chính user.

Memory flow: pending proposal card → preview/sửa text → confirm đúng version khi AI+MEM effective → receipt → badge approved. C-MEM bật không tự approve; lưu private không tự memory; rejection không tạo approved record. Nếu source/consent đổi lúc dialog mở, server trả expired/conflict, giữ bản sửa của user ở RAM để họ có thể chủ động tạo lại, không tự resume approval cũ.

Chỉnh/xóa private source đã liên kết phải cảnh báo hệ quả PD-05 như UI hiện tại: hồ sơ published/dẫn xuất cũ mất hiệu lực; bản sửa không tự được chia sẻ. Nhận invalidation phải clear related queries/room views, không chỉ hide nút. T-MEM-03/04 và T-PRIV-02 chứng minh across tab/reload/restart.

## Hành trình 3 — Publish và matching độc lập AI

Điểm bắt đầu: Tôi→Hồ sơ kết nối hoặc CTA Cầu Nối. User chọn interest/value/style/goal/language, có thể chọn một mapping private→tag bằng explicit checkbox; không gửi raw private text sang published profile. Prototype dùng sampleProfile/PI01 và JSON equality preview; production dùng draftVersion/previewDigest từ server.

Flow thật: sửa draft (throttled save hoặc Save rõ ràng, giữ local draft khi offline) → preview DTO allowlist → bật C-MATCH nếu user chọn → publish expectedVersion → render “Đang chia sẻ” **sau commit** → discovery query. Cancel preview không thay published hiện tại. Publish bản mới/withdraw xác nhận hệ quả đóng phòng cũ; 409 bắt xem preview mới.

Discovery giữ cards/avatar/chips/lý do/“Làm quen/Bỏ qua/Chặn”. Bỏ strings viết cứng theo C01–C04; thay bằng taxonomy templates từ backend. Avatar/bí danh tổng hợp theo cặp không liên quan identity đã reveal. Không thêm free-text bio vì có chỗ hiển thị cardLead. Score dùng test/oracle ở server, UI vẫn hiển thị điểm chung, không xác suất phù hợp tâm lý.

Empty state giải thích thiếu người cùng điều kiện và CTA xem lại lựa chọn/lời mời; không nới teen/block/goal/language hoặc tạo người giả. API unavailable là error state riêng, không biến thành danh sách rỗng hoặc mock fallback. Matching phải hoàn thành demo với **AI và MEM đều tắt**.

## Hành trình 4 — Lời mời, mutual và chat

Điểm bắt đầu: candidate card→Làm quen→Lời mời & kết nối. Prototype cho người điều khiển bấm “Mô phỏng đối phương: Đồng ý/Từ chối/Hết hạn”; real mode chỉ sender cancel, recipient accept/decline. Hai browser/account độc lập là bằng chứng bắt buộc.

Send invitation chờ receipt; limit 10/24h và 10 pending hiển thị Retry-After/trạng thái đúng; stale candidate yêu cầu refresh. Pending không có composer hoặc hidden transcript trong query cache. Cross invitation hoặc double accept trả cùng room, không mở hai route/duplicate room. Request terminal không mở lại sau enable quyền.

Messages list thay state.connections bằng room summaries/current policy. Trong ChatPage, chờ access query trước load messages; 404/403/closed chuyển state/route hiện tại, clear nội dung trong RAM. Human identity/label giữ tách khỏi AI; không auto peer greeting hoặc scripted self message sau room open.

Send text: giữ draft đến khi tạo pending bubble có ID; POST với clientMessageId; ACK reconcile bubble thành persisted; network uncertainty cho “Đang kiểm tra” và tra lại/retry cùng key. Local contact warning hiện tại là nhắc user, không cam kết phát hiện hết PII; server áp policy đã chốt, không log nội dung regex hit. Network lỗi giữ nội dung, 429 chưa gửi không clear input.

Socket ID-only event→query messages sau cursor; offline/reconnect hiển thị status kín đáo, không chặn soạn nháp. Reload page fetch DB history còn quyền/retention; không dựa socket replay tự có. Out-of-order duplicate notify vẫn fetch/reconcile seq; room revoked không fetch text thêm. End/block nhận receipt rồi terminal view; không chờ nhân viên report.

## Hành trình 5 — Reveal, safety và privacy

Reveal: giữ “Chia sẻ từng thông tin”, preview/deny/revoke từng trường/chiều. **Loại peer simulation khỏi real mode.** Requester chỉ thấy pending; owner nhận request và own field preview, grant expected identityVersion; recipient fetch đúng field sau grant. Không cache field trong CandidateDTO/chat message hoặc render sẵn rồi CSS hide. Identity edit thu hồi field cũ; message/reveal queries clear khi invalidation.

Safety: chọn đối tượng từ tương tác thật hoặc room safe reference, reason allowlist, user chọn tối đa 2 bằng chứng mà họ còn quyền chọn. Block dùng riêng, không cần gửi report. Receipt xuất hiện sau server commit, phân biệt submitted/received-for-review/resolved tùy staffing thực; chưa có Q07 thì staging dùng tổng hợp và ghi rõ chưa có vận hành người thật.

Privacy: bốn switch có pending state, tắt giữ confirmation copy và hệ quả cụ thể. Khi request lỗi switch không báo đã tắt; tải lại snapshot và thông báo. Server gate vẫn là quyền chuẩn kể cả UI stale. Xóa dữ liệu trả job status; “đã ngừng sử dụng” và “đã xóa mọi bản tại processor” là hai mốc khác nhau. Export hiện tại chỉ xem số đếm; nếu thêm tải export thật cần scope/reauth/TTL one-use và test peer leakage.

Reset/peer simulation chỉ test harness; product entry không DemoTools, không đặt lại “nhân vật An” hoặc bật lại consent. Thao tác account deletion nằm trong Settings có reauth/confirmation và trạng thái job riêng. Không đổi copy quảng bá “Chỉ bạn xem” thành cam kết processor không lưu nếu chưa có bằng chứng privacy gate.

## Voice: thêm nhỏ, không đổi thành voice agent liên tục

Hiện chưa có recorder trong BotConversation; VOICE_* chỉ mock trong reducer. Phase 7 thêm nút mic/recorder ngay composer, dùng UI components hiện tại. C-AI+VOICE effective và **hành động user** mới gọi getUserMedia; model không tự mở mic. Recording tối đa 30 giây, có timer/stop/cancel, không audio emotion inference, không always-listening.

Contract đề xuất: `POST /voice/transcriptions` multipart bounded audio + conversationId/clientRecordingId → 202 transcriptionId hoặc validated transcript; `GET /voice/transcriptions/:id` trả trạng thái/text tạm; `DELETE /voice/transcriptions/:id` cancel/purge. Server kiểm owner/bot/AI+VOICE, byte/duration/MIME; transcript/audio cùng kho tạm, audio xóa sau success/cancel/error và tối đa 15 phút. Provider request ID/usage metadata tách khỏi audio; processor retention cần Q02 trước dữ liệu thật.

Flow: nhấn ghi → browser permission → recording → stop → STT pending → **user xem/sửa chữ** → gửi như text chat bằng hành động riêng. Mic denied/unsupported/timeout/upload failed/AI+VOICE revoke/route leave đều có cleanup tracks/blobs và fallback text; không tự gửi transcript sau STT. Không tắt chat text khi VOICE tắt. T-VOICE-01/02 kiểm cả frontend và backend cleanup bằng fake processor; native mobile recording và provider integration vẫn cần nghiệm thu riêng.

Voice là yêu cầu Must được thuật lại trong docs/prompt, cần xác minh Charter Q01; text-only spike không xóa nghĩa vụ đó. Không thêm realtime voice pipeline chỉ vì SDK có hỗ trợ.

## Giữ giao diện, accessibility và mobile

- Giữ tokens, sage palette, bot SVG, roster, bottom-nav, dialogue/cards, scoped GSAP/cleanup và reduced motion. Captures baseline tại [manifest](validation-artifacts/visual/manifest.json).
- Async mutation thông báo bằng status/alert, không focus mỗi stream chunk. Dialog giữ focus trap/restore/cancel-first; lỗi validation gắn field và summary phù hợp, không chỉ toast tự mất 3 giây.
- Mobile giữ visualViewport/safe-area, composer hiển thị khi keyboard mở, scroll không nhảy khi user đọc cũ. Kiểm 360/375/390/430/768/1280/1440; thêm zoom 200%, reflow, font tiếng Việt dài và touch targets. Physical devices/iOS không được suy ra từ viewport emulation.
- Không redesign tiny text đồng loạt trước có evidence; cải thiện chỗ gây đọc khó/target khó theo task P07.03, kèm before/after captures và keyboard/a11y checks.
- Bundle/perf: giữ import trực tiếp icons, batch stream updates, query song song các nguồn độc lập; không thêm memo/lazy framework đại trà. Rerender profiling và lazy routes chỉ khi đo được vấn đề; [React guidance](https://react.dev/learn/you-might-not-need-an-effect) là tham khảo cần đọc lại khi implementation dùng pattern cụ thể, không phải nguồn đã audit runtime ở đây.

## Rollout và rollback frontend

Chuyển từng feature bằng typed API adapter ở composition root; fixtures chỉ test injection. Real mode mặc định fail-closed nếu env/session/API thiếu, không fallback sang demo. Feature flags chỉ mở/khóa capability, không cấp quyền hoặc biến API failure thành mock success. Không nhúng secret trong VITE_*.

Checkpoint mỗi slice: happy path→error/409/429→revoke khi pending→reload đúng semantics→keyboard/mobile regression. Nếu feature real lỗi, disable entry bằng flag và giữ dữ liệu server; capability chưa sẵn phải unavailable, không mock success. Sau phase 7 kiểm import graph/bundle để real entry không gọi fixtures/demo scheduler/scripted peer actions.

Product UI không nhãn Prototype/Demo/Experimental hoặc “chỉ mô phỏng”. Privacy/safety/consent/eligibility giữ nguyên. Login qua backend Supabase Auth→opaque app cookie; không tokens localStorage, không tự cấp age/role. Missing config/API failure giải thích tự nhiên, giữ draft/retry, không synthetic success.
