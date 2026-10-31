# Public landing and interactive onboarding design

> Superseded age policy (2026-10-31): MoodPrint now requires self-declared **18+ across all functionality**, including guests. Earlier 16+ design statements are historical; use the [current rollout policy](../release/moodprint-18plus-0020-rollout.md).

**PROPOSED, not implemented.** Verdict: **CONDITIONALLY_READY**, dependent on guest contracts and tour accessibility/compatibility proof. Preserve MoodPrint's existing visual identity; this is an extension of the current product, not a rebrand.

## 1. Current constraints and route strategy

The app mounts `RealApp` unconditionally (`frontend/src/main.tsx:1–11`), then HashRouter → `SessionRoot` → `/session` → AuthScreen or protected shell (`RealApp.tsx:191–278,1918–1923`). Public pages cannot be added merely as another Shell route. The auth callback is a real `/auth/callback` path with token-bearing fragment/query that must be consumed and cleared before rendering (`Auth.tsx:17–33`).

**Recommended low-disruption route topology:**

| URL | Proposed behavior |
|---|---|
| `/` | Public landing rendered immediately, without creating any app/Supabase session. An optional background `/session` read can show **Tiếp tục sử dụng** for a valid existing session; failure must not block public content |
| `/#/login` and `/#/login?mode=signup` | Existing AuthScreen with route-selected mode, public to unauthenticated visitors. Valid registered users can continue their existing app. Guest registration transition uses explicit end/disclosure |
| `/auth/callback` | Existing parser runs before route selection, removes secrets and preserves confirmed/recovery/error behavior. Never parse a recovery token as an app hash route |
| `/#/assistants`, `/#/self`, `/#/memory`, `/#/settings`, etc. | Preserve current app URLs and protected session/eligibility behavior |
| `/#/feedback` | Protected submission for valid guest/registered users. No-session visitors arriving from landing see a concise explanation and trial/login CTA rather than a broken form |
| `/#/admin/feedback` | Permanent admin with live server role check; client route is only a convenience gate |

Create a small `AppEntry.tsx` for public/app boundary and lazily load the protected app from the landing entry. Move callback handling to a single owner; do not call `readAuthCallback()` independently in two mounts and erase the token before the intended consumer sees it. Preserve existing exported hooks/components or split them narrowly to avoid circular imports from the public page into a 1900-line app module (`RealApp.tsx:1–87`). Leave a compatibility entry for old `/#/` that resolves to the app/auth flow. Public `/` intentionally gains a welcome page; existing app deep links retain behavior and existing sessions are never replaced.

Alternative: migrate everything to BrowserRouter with `/app/...` and legacy redirects. This makes clean URLs easier, but changes every deep link, callback/back behavior and existing E2E fixture; defer that larger migration. A static/prerendered landing is compatible with the recommended topology and provides meaningful HTML for search/social previews without moving protected content to SSR.

Caddy already serves SPA fallbacks and reserves `/api` (`deploy/Caddyfile:15–31`); FastAPI static serving also has an API-safe fallback (`backend/app/main.py:295–311`). Test both before changing edge config. Do not cache authenticated HTML/API responses, guest creation or tokens. Hash routes do not create useful independent SEO pages: put indexable product content in public root HTML, use canonical `/`, Vietnamese title/description/Open Graph image, and noindex for auth/private/admin surfaces. `frontend/index.html:1–24` already has Vietnamese language/title/description; preserve and refine them rather than introducing external trackers or fonts.

## 2. Landing information architecture and Vietnamese copy

Primary job: a visitor understands what can be tried, how private use differs from social sharing, and can start without entering email. No medical efficacy, real-user counts, testimonials or security certification claims without evidence.

| Section | Layout and content | Suggested copy |
|---|---|---|
| Header | Brand; short links **Trợ lý**, **Cảm xúc**, **Quyền riêng tư**, **Câu hỏi**; **Đăng nhập / Đăng ký**. Mobile uses compact accessible menu | Keep existing MoodPrint wordmark/avatar identity |
| Hero | Desktop text + one authentic synthetic-data product capture; phone text first, image second. One dominant CTA and one secondary action | **Hiểu mình hơn, kết nối chân thành hơn.** / **Ghi lại cảm xúc, trò chuyện cùng 5 trợ lý và khám phá điều quan trọng với bạn.** |
| Entry actions | **Dùng thử 2 giờ** opens guest disclosure/age entry; **Đăng nhập / Đăng ký** opens normal auth | **Không cần email để dùng thử. Không gian riêng dành cho người từ 16 tuổi.** |
| Product proof | Three concise examples: conversation starter, mood entry, approve/discard memory. Use actual current UI with synthetic text; captions explain action | **Bắt đầu bằng một điều bạn đang nghĩ.** / **Ghi lại cảm xúc theo nhịp của bạn.** / **Bạn chọn điều trợ lý được ghi nhớ.** |
| Five assistants | Five small avatar/name/one-sentence descriptions; readable grid/list, no auto-rotating carousel | Mây: **Có một điều muốn kể? Mây ở đây để lắng nghe.** Gương: **Khám phá sở thích và điều bạn coi trọng.** Nhịp: **Nhìn lại cảm xúc, chọn một thói quen nhỏ.** Rủ Rê: **Cùng giải đố, học hỏi hoặc thử điều mới.** Cầu Nối: **Tập mở lời và tìm điểm chung để kết nối.** |
| Journaling | One focused screenshot, explain optional note, no diagnostic claims or fabricated sample of a guest's real week | **Hôm nay bạn thấy thế nào? Một dấu ghi nhỏ để nhìn lại chính mình.** |
| Social safety | Distinct registered-only explanation; public profile preview/explicit publish, adult eligibility, block/report. Do not expose real people | **Kết nối khi bạn sẵn sàng.** / **Tìm bạn và nhắn tin dành cho người từ 18 tuổi có tài khoản. Bạn chủ động chọn thông tin chia sẻ.** |
| Privacy/trial | Deadline, active-store cleanup, permission controls, approved memory and feedback exception. Link to full plain-language policy | **Dùng thử trong 2 giờ. Khi hết giờ, bạn không thể mở lại dữ liệu của lượt này.** Explain cleanup/backup/provider limits without burying them |
| FAQ | Four to six native `<details>` questions; no accordion that requires a mouse | See below |
| Footer | **Góp ý cho MoodPrint**, privacy, replay/help entry for app, final trial CTA | **Có điều gì chưa thuận tiện? Chia sẻ với MoodPrint.** |

Assistant facts come from `backend/app/ai/registry.py:3–44` and current contextual descriptions `AssistantGuide.tsx:3–34`. Present five personalities without promising five unrelated technical models. Clarify guests can talk with Cầu Nối but cannot search or message real people. Individual Rủ Rê AI play is supported; structured multiplayer activities remain registered-only (`activities/routes.py:65–142`).

FAQ copy:

- **Có cần tạo tài khoản không?** — **Bạn có thể dùng thử 2 giờ mà không cần email. Tạo tài khoản khi muốn tiếp tục sử dụng lâu dài.**
- **Hết 2 giờ thì sao?** — **Lượt dùng thử kết thúc và dữ liệu của lượt này không mở lại được. Bạn có thể bắt đầu lượt mới với dữ liệu trống.** Link to precise cleanup/retention disclosure.
- **Người khác có thấy cuộc trò chuyện của tôi không?** — **Cuộc trò chuyện với trợ lý và nhật ký không được dùng làm hồ sơ tìm bạn. Bạn chủ động chọn thông tin muốn chia sẻ.** Explain authorized service processing/staff scope in full privacy policy; do not say nobody can ever access infrastructure.
- **Dùng thử có tìm bạn được không?** — **Tìm bạn và nhắn tin cần tài khoản, xác nhận đủ 18 tuổi và quyền chia sẻ do bạn bật.**
- **Trợ lý có thay chuyên gia chăm sóc sức khỏe không?** — **MoodPrint hỗ trợ trò chuyện và tự nhìn lại; không thay thế tư vấn hay điều trị chuyên môn.**
- **Góp ý có bị xóa cùng lượt dùng thử không?** — **Góp ý bạn chủ động gửi được lưu riêng theo thời hạn đã thông báo, không kèm cuộc trò chuyện hay nhật ký.** Publish only with the approved feedback retention policy.

## 3. Established visual system and reusable elements

Verified visual authority: `tokens.css:1–59`, `components/UI.tsx:1–146`, `companions/registry.ts`, `companions/Avatar.tsx`, `styles/me2we.css`. Keep off-white background, forest-green primary, warm accent, dark green text, system typography, rounded controls, generous spacing and companion avatars. Use current semantic tokens; no unrelated purple/neumorphic theme, new font service or decorative AI hero artwork. The UI UX Pro Max exploration was advisory; its generic theme/testimonial suggestions were rejected where they conflicted with actual brand and available product evidence.

Reuse Brand, Button, Dialog, StatePanel, focus utilities and existing GSAP. Prefer new focused components `LandingPage`, `GuestEntry`, `GuestStatus`, `GuestExpired` and `TourController`; do not add a new UI framework. Existing GSAP owners include Dialog (`UI.tsx:74–89`), ConversationInfo, ActivityDock and AIActivityStatus. A tour must not animate the same transform/scroll/focus concurrently with them.

Use authentic screenshots captured later from current synthetic fullstack actors, not production private sessions. Existing live audit screenshots show only login and cannot stand in for the core product. Capture version/viewport in the asset source record; crop only irrelevant chrome, keep honest UI, redact synthetic fixture identifiers if visible. Optimize AVIF/WebP with width/height, load below-fold images lazily, meaningful alt captions; avoid making text inside screenshots the only explanation. Do not commit raw browser state, traces or screenshots by default.

## 4. Spotlight library evaluation

Registry metadata inspected on 2026-10-28 (no dependencies installed): Driver.js **1.10.2 MIT**; React Joyride **3.2.0 MIT**, React/ReactDOM peer `16.8–19`; `@reactour/tour` **3.8.0 MIT**, React peer includes 19. These registry statements are compatibility hints, not tested runtime guarantees.

| Option | Strength | Integration cost / risk | Recommendation |
|---|---|---|---|
| Driver.js | Small framework-independent spotlight, configurable hooks/buttons/keyboard/scroll; can lazy load outside normal app path | Imperative lifecycle, route coordination, StrictMode cleanup, focus/ARIA/CSP/mobile need proof against exact pinned release | Preferred candidate, conditional on acceptance spike |
| React Joyride | React-oriented step state, controlled tour and event callbacks | More adapter/dependency surface; verify current release API and styling/accessibility under React 19 | Fallback candidate if Driver proof fails |
| Reactour | React provider/hooks; controlled tour composition | Extra provider and masking/focus configuration; same dynamic route/mobile proof needed | Viable alternative, no reason to add alongside another tour library |
| Custom portal/overlay | Full product control, no library | Must build correct positioning, clipping, focus, scrolling, resizing and SR interaction; largest maintenance burden | Avoid for MVP unless library proof fails with documented reason |

Driver's current docs expose lifecycle/configuration hooks and keyboard/animation controls, but not a guarantee of conformance for this app. [Driver.js configuration](https://driverjs.com/docs/configuration), [official repository](https://github.com/kamranahmedse/driver.js). Pin one tested release and lockfile only during implementation. Do not assume latest-doc options such as wait/skip helpers exist in 1.10.2; the application adapter must handle missing/dynamic targets itself. Do not install multiple alternatives to compare on production.

## 5. Optional, replayable tour

Ask **Muốn xem hướng dẫn nhanh?** after the user reaches an understandable app state. Default is no automatic overlay; a **Xem hướng dẫn** action in settings/help is always available. Never start on consent dialogs, microphone prompts, active emotional conversations or while an AI answer is arriving. A visitor can get product value without completing a tour.

Keep initial tour to four steps, about one minute. Registered adults may opt into one additional connection introduction. Navigation can change routes, but it must never submit an action or toggle a permission.

| Step | Route and stable proposed target | Note / behavior |
|---|---|---|
| 1. Trợ lý | `/#/assistants`, `[data-tour='assistants-list']` | **Chọn trợ lý hợp với điều bạn muốn làm hôm nay. Bạn có thể đổi bất cứ lúc nào.** Highlight list/heading without sending a message |
| 2. Cảm xúc | `/#/self`, `[data-tour='mood-entry']` | **Ghi lại cảm xúc của bạn. Ghi chú là tùy chọn và vẫn là thông tin riêng.** Do not fill or save |
| 3. Ghi nhớ | `/#/memory`, `[data-tour='memory-intro']` | **Trợ lý chỉ ghi nhớ khi bạn duyệt. Bạn có thể sửa hoặc xóa sau.** Use intro/empty state if none exists; never auto-approve or read memory aloud |
| 4. Quyền riêng tư | `/#/settings`, `[data-tour='privacy-controls']` | **Bạn chọn quyền xử lý dữ liệu và có thể rút lại bất cứ lúc nào.** Guest variant reminds **Dữ liệu của lượt thử kết thúc sau 2 giờ** |
| Optional adult registered step | `/#/connect`, `[data-tour='matching-intro']` | **Bạn chủ động xem trước và chọn thông tin chia sẻ để tìm bạn.** If ineligible/no MATCH consent show explanation only, not a permission bypass |

Guest configuration excludes social tour step. Guest navigation retains a single discoverable locked **Tìm bạn** explanation; hides real-message tab or replaces it with the same explanation without polling/loading rooms. Keep personal sections prominent. Review `Navigation`/`useSocialSummary` (`RealApp.tsx:328–374`) and `AssistantGuide` links (`AssistantGuide.tsx:23–33`) together so the tour does not lead into unauthorized requests.

Controller contract proposal: `TourController` consumes `session.accountKind`, capability/eligibility, current route and motion policy. Step definitions contain `id`, `route`, `target`, static localized title/note and `isApplicable(session)`. `goToStep(id)` navigates, waits for route/resource readiness and visible target (max 3 seconds), settles current GSAP geometry, then highlights. It cancels prior waits on route changes/unmount and checks guest deadline. Missing optional target is skipped with a useful fallback; missing critical first target shows **Chưa thể mở hướng dẫn ở màn hình này. Thử lại sau.** It must not render an off-screen spotlight at `(0,0)`.

Controls: **Tiếp**, **Quay lại**, **Bỏ qua**, **Hoàn tất**, and **Bước 2/4**. Escape skips/closes. Close is always available; no backdrop click advances unexpectedly. Back uses prior applicable tour step; browser Back cancels or resynchronizes, not a navigation loop. On finish restore focus to a visible launch control or destination heading. Preserve unsent app drafts through navigation as current routes allow; warn/offer to exit rather than start a route-changing tour from a nonempty draft.

Track `tourVersion`, skipped/completed and prompt-dismissed without personal content. Guest state is scoped to the lifecycle and cleared at end; do not retain a user-linked guest preference beyond deletion. Registered MVP may use user-scoped local preference with reset/replay; avoid device fingerprinting. Replay is always possible even after skip/finish. Broadcast only state signals across tabs; do not sync private content.

## 6. Accessibility, motion and responsive acceptance

- Visible semantic heading and named note; programmatic title/description association. One current popover and one active focus owner. Preserve real target's accessible name and content; use static text, not untrusted HTML strings.
- Keyboard can reach Next/Back/Skip/Finish and the intended target without falling into dimmed controls. Escape always closes; return focus correctly. Do not set `aria-hidden`/`inert` on an ancestor containing the active target/popover. Screen-reader-only step list is available when spotlight positioning cannot be used.
- Coordinate native `<dialog>` top layer: suspend tour during dialogs or close before them; z-index alone cannot override the top layer. Route-heading focus runs once, then tour moves focus deliberately (`useRouteFocus.ts`; `UI.tsx:91–146`).
- Honor `prefers-reduced-motion` using `useMotionPolicy.ts:24–40`: no spotlight tween or smooth scrolling when reduced; pause when hidden. GSAP only owns presentation, never eligibility or session timers.
- Test 320, 390, 768 and 1280/1440 widths, portrait/landscape, soft keyboard and 200% text. Notes must fit viewport, flip above/below, avoid bottom navigation/composer and not force horizontal scroll. On phones use a compact bottom note with target still visible; fall back to inline instructions if spotlight geometry is unsafe.
- Text contrast ≥4.5:1, meaningful non-text/focus contrast ≥3:1; target controls ideally 44×44 CSS pixels with spacing. Do not use dim overlays that make the highlighted text unreadable. Mark rating states by text/state as well as color.
- Watch resize/scroll/target changes with a bounded observer, call the adapter's refresh only when layout stabilizes, and clean listeners/portals on unmount, expiry or StrictMode remount. Never poll forever for an absent route target.

These are design acceptance requirements, not verified tour behavior. Existing web guidance consulted: [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md). Existing login alone had zero automated axe violations; no inference is made about future tour or authenticated screens.

## 7. Copy and state changes tied to guest context

| Current source / issue | Required new variant |
|---|---|
| `AIData.tsx:163–170`: promises retention in days and other-device continuation | **Lưu trong lượt dùng thử này. Lịch sử không mở lại được sau khi hết giờ.** Keep default opt-in behavior and explain restart loss for unsaved RAM chats |
| `RealApp.tsx:321–323`: says quota resumes tomorrow | **Bạn đã dùng hết lượt trò chuyện của lượt dùng thử.** Offer account creation without implying a quota reset or data migration |
| `Privacy.tsx:108–139`: password reauth/deleted-account screen | **Kết thúc và xóa lượt dùng thử**, no email/password. Show asynchronous cleanup truthfully |
| `AssistantGuide.tsx:23–33`: social actions from Rủ Rê/Cầu Nối | Guest-specific **Tìm hiểu về kết nối** explanation; keep AI conversation usable |
| Existing `Cảm xúc` / `Moods` / `Nhật ký tâm trạng` naming | Navigation **Cảm xúc**, screen heading **Nhật ký cảm xúc**, primary action **Lưu cảm xúc**; use consistently in landing/tour/feedback |
| Empty trial data | **Chưa có cảm xúc nào được ghi. Bắt đầu từ hôm nay nhé.** / **Chưa có ghi nhớ được duyệt. Bạn luôn là người quyết định.** No fabricated success/history |

Loading: labelled progress, retain public content while background auth loads. Provider/guest-start failure: preserve entered age/disclosure choice, let user retry safely, never open a fake app. Expired: distinct from network failure and ordinary login error. Feedback failure: keep input only while session valid; after expiry clear private draft, explain a new trial is needed. All time warnings should be quiet and nonintrusive.

## 8. Implementation targets and verification

Create focused public/guest/onboarding feature files; modify `main.tsx`, `Auth.tsx`, the Shell/navigation sections of `RealApp.tsx`, `AssistantGuide.tsx`, `AIData.tsx`, `Privacy.tsx`, `index.html` and tokens only when a new semantic token is necessary. Do not rewrite the chat engine or replace existing CSS conventions.

Before release run route/callback/deep-link tests, public page with API offline, no-creation network assertion, guest/registered navigation, tour skip/replay/back/missing-target/expiry tests, keyboard and SR manual review, reduced-motion/200% text and mobile/desktop screenshots. New automated file names and phase gates are specified in [05](05-implementation-roadmap.md) and [06](06-testing-and-release-plan.md).
