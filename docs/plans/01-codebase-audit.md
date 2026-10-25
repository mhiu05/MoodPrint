# 01 — Audit codebase hiện tại

> **Audit lịch sử trước implementation, 23/10/2026:** toàn bộ inventory, versions, source line anchors, hashes và test results dưới đây phản ánh checkout ban đầu. Không dùng nhận định “backend trống/chưa SDK” làm trạng thái hiện tại. Target đã đổi sang Python/FastAPI/Supabase/Agents SDK Python; xem [03](03-target-architecture.md) và [10](10-decisions-and-open-questions.md).

Các liên kết tới frontend prototype đã được pin vào commit `dad0cb46bf69417a7b87e60e4e745c0a8c77df71`, snapshot ngay trước khi productization thay thế cây frontend cũ.

Ngày audit: 23/10/2026. Phạm vi: toàn bộ file source, CSS, assets, tests, cấu hình và tài liệu có trong checkout; không khảo sát tài khoản cloud không được chỉ định. **Source là prototype, không phải frontend production hoàn tất.**

## Repository và nguồn thực tế

```text
MoodPrint/
├── .gitignore                 # giữ nguyên
├── .env.example               # file rỗng
├── README.md                  # 2 dòng mô tả MoodPrint
├── LICENSE
├── agents/                    # trống, kể cả file ẩn
├── backend/                   # trống, kể cả file ẩn
├── docs/
│   ├── technical-poc-architecture.md
│   └── prompt.md
└── frontend/
    ├── src/{companions,components,domain,mocks,pages,state,styles}
    ├── public/{me2we.svg,may.svg}
    ├── tests/{e2e/journeys.spec.ts,production-smoke.mjs,screenshots.mjs,visual-review.mjs}
    ├── package.json, package-lock.json, vite.config.ts, tsconfig.json
    ├── playwright.config.ts, index.html, README.md, .gitignore
    └── node_modules/, dist/    # sẵn trong môi trường, không phải bằng chứng deploy
```

`rg --files --hidden` đã loại `.git`, node_modules, dist và artifacts khi kiểm kê. Không có AGENTS.md, repository skills, `.agents/`, `.codex/`, PRODUCT.md, DESIGN.md, CI workflows, Dockerfile, SQL, migrations hoặc backend manifest. Hướng dẫn không sửa `.gitignore` được nhận trực tiếp từ người dùng và áp dụng đầy đủ.

Git ban đầu chỉ theo dõi `.gitignore`, LICENSE, README; `.env.example`, docs và frontend đã là untracked trước audit. Vì vậy `git diff` đơn thuần không đủ phát hiện source untracked bị sửa; dùng SHA-256 baseline để đối chiếu sau khi viết plans. Không stage/commit/push trong lượt này.

**Đã tìm đúng tài liệu** “Me2We — Thiết kế kỹ thuật AI, bot và ghép cặp để kiểm chứng PoC”, ngày 23/10/2026, [dòng 1–15](../technical-poc-architecture.md#L1). File này 551 dòng, trạng thái PROPOSED. `docs/prompt.md` là prompt nghiên cứu, không phải bản Charter/spec được duyệt. Các đường dẫn `prototype/`, `documents/prototype/`, `2-requirements/2.1…`, `2.4…`, `2.5…` được nhắc đến không tồn tại. README frontend dẫn IMPLEMENTATION-REPORT/evidence cũ không có trong checkout ban đầu. Không tự khôi phục hoặc sửa tài liệu ngoài plans.

## Stack, versions và cách chạy

| Thành phần              | Khai báo                              | Version lockfile/môi trường đã đọc                   |
| ----------------------- | ------------------------------------- | ---------------------------------------------------- |
| Runtime/package manager | Không pin engines hoặc packageManager | Node 24.13.0, npm 11.6.2 tại máy audit               |
| React / React DOM       | `^19.2.0`                             | 19.3.1 / 19.3.1                                      |
| Router                  | react-router-dom `^7.9.4`             | 7.18.4; **HashRouter**, không SSR                    |
| Build                   | Vite `^7.1.10`, plugin-react `^5.0.4` | 7.3.7 / 5.2.0                                        |
| TypeScript              | `~5.9.3`                              | 5.9.3, strict, noEmit, ES2022, Bundler resolution    |
| Motion/icons            | GSAP, @gsap/react, lucide-react       | 3.15.0 / 2.1.2 / 0.468.0                             |
| Unit                    | Vitest `^3.2.4`                       | 3.2.7, 2 test files, node environment                |
| Browser/a11y            | Playwright, axe-core wrapper          | @playwright/test 1.64.1, @axe-core/playwright 4.14.0 |

Version ở bảng được đọc từ lockfile, không phải khẳng định “latest”. Chưa có SDK OpenAI, API client, server-state library, auth, SQL driver, Socket.IO hoặc job dependency. npm là lựa chọn phù hợp để tiếp tục; không có bằng chứng cần đổi package manager.

[Entrypoint](../../frontend/src/main.tsx#L1) bọc StrictMode, import tokens/global/me2we CSS rồi render App. [App](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/App.tsx#L31) chứa ScreenGate, Shell, navigation, route guards, inline MessagesPage và Provider. [Vite config](../../frontend/vite.config.ts#L1) dùng base `./`, dev 5173 strictPort; `build` chạy tsc rồi vite build, preview 4173. Không có API proxy hoặc env schema. `.env.example` rỗng.

## Inventory theo trạng thái

Định nghĩa: IMPLEMENTED = có hành vi đúng trong phạm vi kiểm tra; PARTIAL = có một phần; MOCK = dữ liệu/tác động giả; MISSING = không có; UNKNOWN = thiếu bằng chứng. Có thể ghi IMPLEMENTED cho thuật toán thuần trong prototype và MOCK cho luồng sản phẩm sử dụng nó.

| Nhóm                                                 | Trạng thái                                           | Bằng chứng và giới hạn                                                                                                                                       |
| ---------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Render/navigation/motion                             | IMPLEMENTED trong prototype                          | App routes, UI.Motion/Dialog; build/unit/browser checks ở cuối tài liệu                                                                                      |
| Năm bot, danh tính, threads/cards                    | PARTIAL UI + MOCK phản hồi                           | [registry.ts](../../frontend/src/companions/registry.ts#L1), [scriptedReply](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/scenarios.ts#L4), reducer `AI_BOT_*` dòng 257–346 |
| Mood CRUD/summary                                    | IMPLEMENTED tính toán; MOCK persistence              | [moodSummary](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/domain/mood.ts#L4), reducer `MOOD_SAVE` dòng 478; RAM và ngày mẫu                                                           |
| Private profile/memory                               | PARTIAL UI/policy + MOCK lưu trữ                     | Profile.PrivateProfile, policies.memoryContext dòng 116; flag memory không được nạp vào scriptedReply                                                        |
| Matching                                             | IMPLEMENTED pure scoring; MOCK discovery nhiều người | matching.score dòng 8, recommendations dòng 48; candidates fixture                                                                                           |
| Consent/age/authorization                            | PARTIAL guard client                                 | policies dòng 3–83; demo seed adult và cấp quyền; không có server identity                                                                                   |
| Invitations/connection/reveal/block                  | IMPLEMENTED mô phỏng tuần tự; MOCK liên người        | reducer `openConnection`, `REQUEST_*`, `REVEAL_*`; không có transaction hai user                                                                             |
| Human chat/realtime                                  | MOCK                                                 | reducer `HUMAN_FINISH` dòng 760 dùng peerReplies và timer, không network                                                                                     |
| ACT01                                                | IMPLEMENTED state machine demo + MOCK peer           | reducer dòng 918–1044, Chat.ActivityPanel; scope production chưa được duyệt                                                                                  |
| Voice/STT                                            | MOCK domain, MISSING UI ghi âm thật                  | reducer dòng 450–477, permissionCopy.VOICE; chưa getUserMedia/STT, composer bot không có mic                                                                 |
| Report/export/delete                                 | MOCK UI/domain                                       | Settings.Safety; safeExport chỉ trả số đếm/danh mục, DELETE_TYPE chỉ RAM                                                                                     |
| Backend, Agents SDK, auth, DB, jobs/outbox server    | MISSING                                              | backend/agents trống, dependencies không có, không SQL/server code                                                                                           |
| Deployed cloud, CI, provider policy, real-model eval | UNKNOWN hoặc MISSING trong repo                      | Chưa truy cập cloud; không cấu hình/bằng chứng trong checkout                                                                                                |

## Frontend inventory và component hierarchy

```text
main → App → Provider(useReducer + Scheduler) → HashRouter → Shell
  ├── Navigation: Trợ lý | Tìm bạn | Tin nhắn | Tôi
  ├── ScreenGate → CompanionsPage → roster + BotConversation → InlineCardView
  ├── ScreenGate → SelfPage → MoodPage | Week
  ├── ScreenGate → ProfilePage → PrivateProfile | Sharing → Preview
  ├── ScreenGate → ConnectPage → discovery | Requests | TeenConcept
  ├── ScreenGate → MessagesPage (inline App.tsx)
  ├── ScreenGate → ChatPage → reveal/options/ACT01
  └── ScreenGate → SettingsPage → Privacy | Safety | DemoTools
```

| Route/màn hình có thật                   | Hành vi/điểm bắt đầu                                                                                                           | Source                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `/assistants`, `/assistants/:botId`      | Mở app vào roster, search bot, intro, starter, chat/card; mobile tách roster và conversation                                   | [CompanionsPage/BotConversation](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/Companions.tsx#L30) |
| `/messages`                              | Danh sách phòng được canChat cho phép; empty CTA sang Tìm bạn                                                                  | [MessagesPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/App.tsx#L397)                                    |
| `/self?tab=mood                          | week`                                                                                                                          | Tự chọn 1–5, note 120 ký tự, sửa/xóa; thống kê 7 ngày, ngày thiếu là null          | [SelfPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Self.tsx#L19)         |
| `/profile?tab=private                    | sharing`                                                                                                                       | “Một chút về tôi”, nhận xét xác nhận/sửa/xóa; nháp → preview → chia sẻ             | [ProfilePage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Profile.tsx#L27)   |
| `/connect?tab=discover                   | requests`                                                                                                                      | Candidate cards/lý do, Làm quen/Bỏ qua/Chặn; requests, mô phỏng peer accept        | [ConnectPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Connect.tsx#L29)   |
| `/chat/:connectionId`                    | Kiểm visibleChat trước composer; human prompts, cảnh báo contact, reveal từng chiều, kết thúc/chặn; activities qua query panel | [ChatPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Chat.tsx#L26)                                  |
| `/settings?tab=privacy                   | safety`                                                                                                                        | Bốn quyền, delete/export mẫu, tên demo, block/report, reset                        | [SettingsPage](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Settings.tsx#L18) |
| `/`, `/start`, `/home`, legacy self tabs | Redirect; không phải onboarding/auth screen                                                                                    | [App routes](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/App.tsx#L241), SelfPage dòng 20                    |

Không có login/register/onboarding/age-input thực, admin moderation inbox, global memory screen hay microphone recorder. Nếu bổ sung sau này phải ghi là màn hình mới; không mô tả như đã có.

## State, hardcode và business logic cần giữ

[Provider](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/state/Provider.tsx#L18) luôn khởi tạo `demoState`, reset lại demo; toàn bộ state ở một Context. [Scheduler](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/mocks/scheduler.ts#L2) dùng setTimeout; [reducer](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/state/reducer.ts#L192) structuredClone toàn state mỗi action. Không có fetch/axios/Socket/WebSocket/localStorage/sessionStorage/IndexedDB trong source ứng dụng. Số lượng state tăng sẽ làm clone, render cả cây và animation nhiều hơn; chưa có bằng chứng cần tối ưu sâu ở kích thước demo hiện tại.

- `initialState` fail-closed, nhưng [demoState](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/mocks/demo.ts#L7) tự START adult, bật AI/MEM/MATCH, publish sample profile cho entry thường, kể cả production build. Production bỏ query fixtures **không đồng nghĩa** production bắt đầu không có consent. Đây là seed demo hợp lý, P0 khi chuyển thành sản phẩm thật.
- `Action.type` là string, payload optional chung ([types.ts dòng 175](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/domain/types.ts#L175)); thread/card domain import từ registry UI; policies/matching import taxonomy trong mocks. Cần extract contract/taxonomy có test, không bê nguyên reducer 1.187 dòng làm backend.
- Mây dùng regex/turn parity; Gương tạo profile card; Nhịp mood/insight; Rủ Rê câu đố/serendipity; Cầu Nối chỉ card điều hướng ([scenarios](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/scenarios.ts#L4)). Không model reasoning/tool/handoff thật. `AI_*` cũ và `AI_BOT_*` cùng tồn tại trong reducer, cần kiểm consumers trước loại bỏ ở phase 7.
- [Cards](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/companions/Cards.tsx#L68) dispatch vào reducer: mood save, profile save/skip, reveal đáp án, Link chuyển bot. Mây→Nhịp chỉ navigate, **không truyền transcript**. Profile card lưu private với `memoryApproved:false`.
- `sourceValid` chỉ nhận PI01→reading ([policies dòng 46](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/domain/policies.ts#L46)); Sharing cũng hardcode PI01. Nguồn private được map thành tag sau lựa chọn, không đưa private text vào profile công khai.
- Matching **45×Jaccard interests + 35×Jaccard values + 20×style**, round-half-up cuối bằng số hữu tỉ; style giống=1, khác có balanced=0,5, direct/listening=0. Ngưỡng 30, tối đa 5, hòa theo ID ([matching dòng 4–104](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/domain/matching.ts#L4)). Oracle: C04 Mầm Xanh 90, C01 Lá Non 78, C03 Nắng Mai 68, C02 Suối Nhỏ 44; C05 không chung ngôn ngữ bị loại. Không đổi trọng số khi port.
- Candidate descriptions/taglines theo C01–C04 là free-text viết cứng tại [Connect dòng 103–133](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Connect.tsx#L103); đây không phải bio field được phép. Preview dùng tên “An”, avatar dùng bí danh fixture, nguồn thật phải trả DTO công khai tối thiểu.
- Request hết hạn 7 ngày, quota 10/24h trượt và 10 pending; chat 20/phút toàn state; cooldown 30 ngày. Chỉ chứng minh xử lý tuần tự RAM, chưa chứng minh concurrency hoặc quota nhiều process.
- Re-publish/withdraw/rút MATCH/sửa-xóa nguồn đã liên kết vô hiệu profile và đóng phòng/grants cũ. Unblock/bật lại không hồi sinh kết nối. Reveal bind field/direction/version; demo cho phép người đang điều khiển mô phỏng quyết định của cả peer.
- Mood clock cố định 22/10/2026, ngày tính UTC+7; UI gắn cứng `/10` ([Self dòng 132, 265, 302](https://github.com/mhiu05/MoodPrint/blob/dad0cb46bf69417a7b87e60e4e745c0a8c77df71/frontend/src/pages/Self.tsx#L132)). Quota/expiry dùng đồng hồ demo, không server time. Đây là task tích hợp lịch/timezone, không đổi công thức biểu đồ.

## UX, forms, accessibility và responsive

**Giữ diện mạo hiện tại.** Palette xanh sage, nền sáng, avatar SVG riêng cho từng bot, font hệ thống Segoe UI/Arial, điểm nhấn Georgia ở welcome; không CDN runtime. Desktop có rail 88px, roster 352px, conversation; mobile dưới 768px có bottom nav 4 tab, chat toàn chiều cao với safe-area và visualViewport. [tokens](../../frontend/src/styles/tokens.css#L1), [me2we.css](../../frontend/src/styles/me2we.css#L17), [UI.Motion](../../frontend/src/components/UI.tsx#L213).

GSAP có scope/cleanup, matchMedia reduced motion; Typing dừng tween khi document hidden. Dialog dùng native dialog, showModal, Tab trap, Escape, focus restore và destructive cancel-first ([UI dòng 88–171](../../frontend/src/components/UI.tsx#L88)). Có skip link, label cho forms, role log/status/alert, native radio/checkbox, accessible mood table. Đây là nền tốt cần giữ khi dữ liệu trở thành async.

Các trạng thái đã có: bot pending/stop/retry/AI-off; search empty; matching loading/error/empty; room closed redirect; mood empty/insufficient; preview validation; consent-off confirmation; report validation/receipt; active-activity leave guard. **Thiếu trạng thái thật:** auth loading/expired, backend unavailable/offline, SSE reconnect/expired/replay, server action pending/409 conflict/429 quota, processing delete, message ACK/failure/retry, backend rejection sau preview.

| Phát hiện                                                             | Mức ưu tiên                | Tác động/khuyến nghị                                                                                                         |
| --------------------------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Success/clear form ngay sau dispatch ở Profile, Self, Settings/report | P1 trước API integration   | Dễ báo đã lưu khi server chưa commit; chờ result, giữ draft khi lỗi, gắn field errors                                        |
| Hardcoded ngày, tên, bio, source PI01, avatar/bí danh mẫu             | P1                         | Sai dữ liệu thật hoặc vượt field allowlist; DTO + formatter, template lý do từ tags                                          |
| Context/reducer global, clone toàn state; CSS override nhiều vòng     | P2                         | Khó bảo trì và có rủi ro stream rerender; tách server state theo feature, delta buffer; chỉ cleanup CSS có visual regression |
| Tiny secondary text 8–11px; một số targets desktop 36–40px            | P2 cần kiểm người dùng     | Không tự kết luận WCAG lỗi từ font-size; đo zoom/reflow, khoảng cách và target ở thiết bị thật                               |
| Không dark-mode/theme switch                                          | Future, không bug baseline | Có tokens nhưng nhiều màu literal ở CSS/SVG; không redesign hoặc thêm theme ngoài scope                                      |

Impeccable source detector trả một finding `side-tab` tại App.module.css:597 (`.published` border-left). Đây là heuristic thẩm mỹ, **không phải lỗi quyền/a11y hay lý do xóa component**; giữ incumbent, không tính là failure chức năng. Không có PRODUCT/DESIGN để so drift. Đánh giá kỹ thuật sơ bộ theo rubric 0–4: accessibility 3, performance 3, theming 2, responsive 3, integrity 3 = **14/20**; điểm là đánh giá engineering có giới hạn, không phải chứng nhận WCAG. Chủ yếu cần `$impeccable harden` cho async states, `$impeccable adapt` cho zoom/mobile, cuối cùng `$impeccable polish` sau tích hợp; không thực thi sửa UI trong lượt này.

## Kiểm tra đã thực hiện và giới hạn

| Kiểm tra                                           | Kết quả ghi nhận                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm.cmd run typecheck` trong frontend             | **PASS**, tsc --noEmit                                                                                                                                                                                                                                                                              |
| `npm.cmd test`                                     | **PASS**, 77 tests: domain 65, companions 12; 2 files; Vitest 3.2.7                                                                                                                                                                                                                                 |
| `npm.cmd run build`                                | **PASS**, Vite 7.3.7; JS 460,26 kB / gzip 150,27 kB, CSS 47,57 kB / gzip 10,23 kB; không phải benchmark tải                                                                                                                                                                                         |
| Existing Playwright journeys                       | Đã chạy; kết quả cuối được đồng bộ tại mục validation của [08](08-testing-evals-plan.md)                                                                                                                                                                                                            |
| Existing visual-review.mjs trên production preview | **PASS**, 12 captures; chỉ đổi đường dẫn/base trong bộ nhớ khi chạy, không sửa script                                                                                                                                                                                                               |
| Quan sát render                                    | [Desktop roster](validation-artifacts/visual/roster-desktop-1440.png), [Mây mobile](validation-artifacts/visual/ai-chat-390.png), [discovery mobile](validation-artifacts/visual/discover-390.png), [profile mobile](validation-artifacts/visual/profile-390.png) và các ảnh còn lại trong manifest |
| Agent-browser                                      | Launcher không mở được CDP trong sandbox, kể cả executable Chromium cụ thể; doctor không tìm lỗi cài đặt. Dùng existing Playwright library thay thế cho captures/checks                                                                                                                             |

Kiểm tra browser dùng Chromium headless, viewport emulation; không có physical touch, iOS/Safari, screen reader thủ công, real keyboard IME trên điện thoại hoặc đo performance thực địa. Chưa chạy API/model/DB/security/concurrency/evals thật vì các thành phần chưa tồn tại. Không dùng kết quả axe ở một số state để tuyên bố toàn sản phẩm đạt WCAG.
