# Public Landing and Guest UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain MoodPrint publicly and provide an honest, accessible trial entry and expiry experience.

**Architecture:** Small public AppEntry lazily loads the existing hash-routed app; one bootstrap callback owner sanitizes credentials before rendering. Server session contract governs guest state, and a lifecycle epoch rejects stale asynchronous results.

**Tech Stack:** Existing React 19/TypeScript/Vite/HashRouter, CSS tokens, GSAP, lucide icons, Vitest pure-module tests and Playwright.

**Spec:** [Approved landing design](../03-landing-onboarding-design.md), [guest copy](../02-guest-auth-design.md#8-guest-experience-and-conversion), [index constraints](00-implementation-index.md#global-constraints).

## Global Constraints

Public /; existing /#/... and /auth/callback preserved. No automatic guest creation on visit, session restore failure or expiry. Existing off-white #f 8f 9f 6, forest #285c 4b, ink #243a 35, system fonts, avatars, CSS tokens and primitives. No rebrand, router rewrite, external trackers/fonts or new UI framework. Read design/UI/React skills during implementation; existing approved design is binding.

## Review Focus

1. Callback parser invoked twice under StrictMode → parse once outside React (GE-08.1).
2. Public landing API unavailable → useful content still renders, no identity (GE-08.2).
3. PublicWrite retry changes key after ambiguous error → preserve key (GE-09.1).
4. Expired user receives an old fulfilled fetch/recording callback → lifecycle epoch drops it (GE-09.2).
5. Registered cookie or unsent trial data during signup → explicit end/disclosure, no silent replacement/transfer (GE-09.1/09.2).

## Component/file contracts

Existing source inspected: main.tsx always imports RealApp; RealApp owns HashRouter/SessionRoot/validateSession/Navigation; Auth.tsx owns readAuthCallback and imports ErrorNotice from RealApp. UI.tsx supplies Button/Dialog/StatePanel/Brand; companions registry supplies all five identities; useMotionPolicy and useRouteFocus already exist.

| Proposed unit                            | Exact responsibility/interface                                                                                                                                                                                                                                                                        |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/features/auth/callback.ts` | Move existing `AuthCallback`, `readAuthCallback(): AuthCallback` without imports from RealApp/React; same URL parsing and replaceState sanitization.                                                                                                                                                  |
| `frontend/src/api/session.ts`            | Move `validateSession(value: SessionView): SessionView`, add required kind/nullability/T/quota checks; no protected UI imports. Reject inconsistent guest delta, nonfinite times and forged staff/matching claims in DTO projection. Backend remains authority.                                       |
| `frontend/src/AppEntry.tsx`              | `AppEntry({callback}:{callback:AuthCallback})`; owns same-origin ApiClient and location/hash listener; root/no hash→LandingPage, any app hash/legacy #/ or nonnull callback→lazy RealApp. Unknown real paths show public not found/landing link; /api not a SPA responsibility.                       |
| `RealApp` narrow entry adjustment        | `RealApp({api,callback}:{api:ApiClient;callback:AuthCallback})`; pass into SessionRoot, remove useState(readAuthCallback), retain HashRouter internally. Callback recovery forces AuthScreen even with existing session.                                                                              |
| `features/public/LandingPage.tsx`        | `LandingPage({api}:{api:ApiClient})`; public content, public experience readiness, optional session read/Continue; never imports RealApp/AIData/social modules.                                                                                                                                       |
| `features/guest/GuestEntry.tsx`          | `GuestEntry({api,onStarted,onClose}:{api:ApiClient;onStarted:(s:SessionView)=>void;onClose:()=>void})`; disclosure/age/CAPTCHA, explicit submit only.                                                                                                                                                 |
| `features/guest/GuestStatus.tsx`         | `GuestStatus({session,remainingMs}:{session:SessionView;remainingMs:number})`; minute display, quiet five-minute notice once, no live per-second announcements.                                                                                                                                       |
| `features/guest/GuestExpired.tsx`        | `GuestExpired({reason,onNewTrial,onRegister}:{reason:'expired'\|'ended';onNewTrial:()=>void;onRegister:()=>void})`; content-free ended/expired screen.                                                                                                                                                |
| `features/guest/useGuestLifecycle.ts`    | `useGuestLifecycle({session,api,onExpired}:{session:SessionView;api:ApiClient;onExpired:()=>void}):{remainingMs:number;epoch:number;signal:AbortSignal;expire:()=>void}`; offset from serverTime, monotonic elapsed for display, focus/visibility/online revalidation, BroadcastChannel signals only. |

In main.tsx evaluate callback **once at module bootstrap before createRoot**; pass immutable result to AppEntry. Do not use a React state initializer with URL mutation. Extract shared ErrorNotice into `frontend/src/components/ErrorNotice.tsx` only if needed by public/guest components; keep a re-export in RealApp to avoid unrelated import churn. Do not move chat/social internals wholesale.

## Exact route/state matrix

| State                            | Public /                                                             | App deep link /#/...                                                                                 | Trial/feedback/social behavior                                                                                                  |
| -------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Unauthenticated                  | Landing immediately; CTA waits readiness; Login/Signup links         | AuthScreen (legacy #/ remains auth/app entry); feedback shows explanation/CTA                        | Never create on GET/load; no form submission without active session                                                             |
| Registered session               | Optional Continue after /session read                                | Existing eligibility/consent/private app, unchanged                                                  | Trial CTA offers Continue; backend 409 never overwrites session; normal social age/consent applies                              |
| Active guest                     | Optional Continue, original deadline                                 | Guest shell/timer and allowed personal functions                                                     | Feedback only before T; matching explanation route, no room/message polling                                                     |
| Expired guest                    | Landing can offer explicit new trial                                 | GuestExpired if client knew guest, otherwise ordinary missing-session screen; old IDs never restored | Clear private state, no retry/new signup automatically; new CTA creates fresh lifecycle                                         |
| Cleanup pending after end/expiry | Public content                                                       | Content-free ended/expired screen                                                                    | “Yêu cầu kết thúc đã được ghi nhận. Dữ liệu đang được xử lý xóa.” Do not poll private jobs after revocation or claim completion |
| Auth service unavailable         | Landing stays usable; “Chưa thể bắt đầu lượt dùng thử. Thử lại sau.” | Error/retry StatePanel; never fake session                                                           | Preserve age input only while entry mounted; ambiguous attempt keeps same key; no new paid call                                 |
| Offline browser                  | Landing HTML/cached assets as available; “Bạn đang ngoại tuyến.”     | Read-only existing display only until conservative deadline; disable mutations, abort at T           | No offline mutation queue; reconnect requires session read before actions                                                       |
| Underage/ineligible              | “MoodPrint hiện dành cho người từ 16 tuổi.”                          | Existing eligibility gate                                                                            | No provider signup for under 16; no AI/MEM/VOICE auto-grant; registered teens retain personal use                               |

Other states: labelled loading; all-empty personal screens; quota exhausted; CAPTCHA failure; consent declined; rate limit with Retry-After; privacy/export/end confirmations; feedback disabled; 401 GUEST_EXPIRED distinct from 503/offline. Retry must not clear unknown provisioning outcome or increment counters again.

## Vietnamese copy and content

Use the detailed approved section/FAQ/assistant copy in audit 03. Required structure: header/anchors, hero, product examples, five assistant cards, journal, registered-only social explanation, privacy/trial, FAQ, footer. Hero “Hiểu mình hơn, kết nối chân thành hơn.” CTA “Dùng thử 2 giờ”, secondary “Đăng nhập / Đăng ký”; entry “Không cần email để dùng thử. Không gian riêng dành cho người từ 16 tuổi.”

Five cards: Mây listens; Gương explores interests/values; Nhịp reflects emotions/small habits; Rủ Rê offers conversational play/learning; Cầu Nối practices opening a conversation. Do not promise guest matching/multiplayer or health treatment.

Trial disclosure “Lượt dùng thử kết thúc sau 2 giờ kể từ khi bắt đầu. Khi hết giờ, bạn không thể mở lại dữ liệu của lượt này.” Expand approved active-store/backup/provider/security-counter notice before public enablement (D01). No published 5-minute guarantee before approval.

Guest variants must also replace **additional inspected RealApp retentionLabel/historyStatus** near chat rendering, not only audit AIData text:

- History: “Lưu trong lượt dùng thử này. Lịch sử không mở lại được sau khi hết giờ.” Unsaved RAM history may disappear on server restart.
- Quota: “Bạn đã dùng hết lượt trò chuyện của lượt dùng thử.” No tomorrow reset.
- Social: “Tạo tài khoản để tìm bạn và nhắn tin. Tính năng này dành cho người từ 18 tuổi, khi bạn chủ động bật chia sẻ.”
- End: “Kết thúc và xóa lượt dùng thử”; register: “Dữ liệu của lượt dùng thử sẽ không chuyển sang tài khoản mới.”
- Expiry: “Lượt dùng thử đã kết thúc”; explicit “Bắt đầu lượt dùng thử mới”, “Tạo tài khoản”, “Về trang giới thiệu”.
- Journal naming: navigation “Cảm xúc”, heading “Nhật ký cảm xúc”, action “Lưu cảm xúc”. Empty “Chưa có cảm xúc nào được ghi. Bắt đầu từ hôm nay nhé.”

## Cache, metadata, CSP and assets

Keep nonhashed HTML/API/auth/guest/feedback no-store; hashed public assets immutable as existing. index.html lang=vi, canonical root, Vietnamese title/description/OpenGraph without fabricated metrics. Put meaningful static heading/intro/FAQ text inside initial root as public fallback for no-JS/search; React replaces it on mount. No protected session data in static HTML. Dynamic noindex for auth/private/admin; real callback path additionally X-Robots-Tag:noindex in both Caddy/FastAPI. Hash app surfaces are not independent indexable server pages.

Measure lazy app boundary: public route must not fetch RealApp/SDK-heavy chat chunks before user navigation; keep build warning visible and compare bundle output with inspected 528.02kB historical main. Existing GSAP imported via shared UI may remain shared; do not claim zero JS. Reuse avatar/product examples; authentic optimized WebP/AVIF screenshots may be captured from synthetic current UI after backend ready, with width/height/alt and below-fold lazy load, no production screenshots. If captures unavailable, labelled illustrative sample cards with text remain honest.

Caddy currently lacks HTML CSP while FastAPI sets it. Align narrow policy in `deploy/Caddyfile` and `backend/app/main.py:CSP`, preserving existing permissions/referrer/microphone rules; no blanket script unsafe-inline/eval. Selected CAPTCHA recommendation is Turnstile, conditional on approved provider setup; allow only documented challenges.cloudflare.com script/frame/connect requirements in both serving modes after compatibility proof. Do not change hosted CAPTCHA settings. Until configuration is verified, readiness keeps CTA unavailable. Driver proof in plan 06 checks actual pinned release against this policy.

### Task GE-08.1 — Add callback-safe public/app boundary

**Objective:** Public root without breaking registered routes/recovery. **Priority:** P1. **Dependencies:** GE-02.2.

**Architecture:** Bootstrap parser outside React, lightweight route classifier, lazy RealApp.

**Files:** Create `frontend/src/AppEntry.tsx`, `frontend/src/features/auth/callback.ts`, `frontend/src/api/session.ts`, `frontend/src/appEntryRoute.ts`; Test `frontend/src/appEntryRoute.test.ts`, extend `frontend/tests/e2e/auth.spec.ts`; modify `frontend/src/main.tsx`, `features/real/{Auth,RealApp}.tsx`.

**Interfaces:** Produces component/parser/validator above; `classifyEntry(pathname:string,hash:string,hasCallback:boolean):'public'\|'app'\|'not_found'`. Do not add component tests requiring a DOM library; existing Vitest includes src/**/*.test.ts, Playwright covers components.

- [ ] Step 1: Write `classifiesLegacyHashesAndCallback`: / nohash public, /#/assistants and #/ app, callback true app. Add E2E “callback is sanitized once before StrictMode render”; intercept history and confirm no token in URL/requests after bootstrap, reset screen still receives token in RAM.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
expect(classifyEntry("/", "", false)).toBe("public");
expect(classifyEntry("/", "#/assistants", false)).toBe("app");
expect(classifyEntry("/auth/callback", "", true)).toBe("app");
```

- [ ] Step 2: Frontend `npm.cmd test -- src/appEntryRoute.test.ts`; `npm.cmd exec -- playwright test --config playwright.owned.config.ts auth.spec.ts` -> expected root/classification assertions fail before change.
- [ ] Step 3: Implement exact boundaries and mode input `AuthScreen.initialMode?:'login'\|'signup'\|'recover'` for #/login?mode=signup; recovery callback wins. Registered valid session deep links continue; login route redirects to assistants after success.
- [ ] Step 4: Same commands ->PASS.
- [ ] Step 5: `npm.cmd run typecheck`; run fixture `real.spec.ts states.spec.ts admin.spec.ts` with owned config; update tests intentionally relying on old public-root login to visit #/login, preserve their assertions.
- [ ] Step 6: Inspect static imports for RealApp→public cycle and parser reuse, history/back behavior and callback error cases.
- [ ] Step 7: Commit `feat(web): introduce public entry with safe auth callbacks`.

**Acceptance:** One callback owner, root identity-free, old hash protected routes preserved. **Edge cases:** recovery while registered, invalid/expired callback, unknown path, browser back. **Rollback:** route to guest-aware app entry; never revert backend guest fences. **Completion evidence:** URL/token sanitization and registered route fixture outputs.

### Task GE-08.2 — Build established-brand landing and readiness states

**Objective:** Useful public Vietnamese page and honest CTA. **Priority:** P1. **Dependencies:** GE-08.1.

**Architecture:** Public text/examples independent of Auth availability; no private import.

**Files:** Create `frontend/src/features/public/LandingPage.tsx`, `landing.css`; Test `frontend/tests/e2e/landing.spec.ts`; modify `frontend/index.html`, `frontend/src/AppEntry.tsx`, `deploy/Caddyfile`, `backend/app/main.py`, `scripts/test_staging_proxy.sh`.

**Interfaces:** Consumes GET /public/experience and optional GET /session; no creation on either. Public CTA opens GuestEntry only after readiness, loaded lazily; until GE-09.1 component exists show unavailable/“Sắp có lượt dùng thử” with login action, not a missing import.

- [ ] Step 1: Add browser tests “public root works with API offline”, “page load sends no guest-intent/signup/create”, “registered Continue preserves session”; assert hero/five assistants/privacy/FAQ/menu keyboard and useful initial HTML.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
await expect(
  page.getByRole("heading", { name: "Hi?u m?nh h?n, k?t n?i ch?n th?nh h?n." }),
).toBeVisible();
expect(identityCreationRequests).toHaveLength(0);
```

- [ ] Step 2: `npm.cmd exec -- playwright test --config playwright.owned.config.ts landing.spec.ts` -> expected missing landing/content fails.
- [ ] Step 3: Implement approved content/tokens/menu/skip link, static fallback/metadata and both-serving-mode CSP/cache changes. Add synthetic asset provenance only when captures exist.
- [ ] Step 4: Same command ->PASS at 320,390,768,1440 widths and reduced motion,200% text; axe plus keyboard proof.
- [ ] Step 5: `npm.cmd run typecheck`, `npm.cmd run build`; Linux/container `bash scripts/test_staging_proxy.sh` after packaging as plan 07; record blocked environment accurately.
- [ ] Step 6: Inspect HTML/network/chunk list and headers for root/callback/API/assets; private/auth no-store, callback noindex, narrow CAPTCHA policy, no external analytics.
- [ ] Step 7: Commit `feat(web): add public MoodPrint landing`.

**Acceptance:** CTA readiness honest, API outage doesn't hide content, no identity on load; keyboard/viewport check observed. **Edge cases:** readiness 503, valid guest Continue, images unavailable, CSP block. **Rollback:** public page remains with CTA disabled. **Completion evidence:** fixture screenshots in temp, axe/keyboard/bundle/header results.

### Task GE-09.1 — Implement explicit guest entry and stable retries

**Objective:** Disclosure/age/CAPTCHA starts or recovers a single lifecycle. **Priority:** P1. **Dependencies:** GE-07.3, GE-08.2.

**Architecture:** Same-origin public-write headers/cookie; persist only nonsecret attempt key as short-lived retry coordination.

**Files:** Create `frontend/src/features/guest/GuestEntry.tsx`, `guestAttempt.ts`; Test `frontend/src/features/guest/guestAttempt.test.ts`, `frontend/tests/e2e/guest.spec.ts`; modify `frontend/src/api/client.ts`, `client.test.ts`, `features/public/LandingPage.tsx`.

**Interfaces:** Extend ApiClient.request options `idempotencyKey?:string;guestIntent?:boolean`: explicitly set Idempotency-Key even with publicWrite and X-Guest-Intent:1 for this flow. Existing authenticated write defaults unchanged. Do not globally discard explicit keys on 409 GUEST_ATTEMPT_PENDING/429/ambiguous response. `beginOrResumeGuest(api:ApiClient,body:GuestInput,key:string,signal:AbortSignal):Promise<SessionView>` creates intent only on explicit initial action, same key on retry. Store random idempotency key+expiry in sessionStorage (no age/CAPTCHA/user/session/provider token),10min; backend cookie is sole ownership secret. Clear on grant/end/T/terminal. Broadcast only busy/ended signals; Web Locks optional.

- [ ] Step 1: Write `publicGuestWriteKeepsExplicitKey`: network failure/409 pending retry headers identical, no automatic new intent; registered 409 shows Continue; under 16 no API. Browser tests doubleclick/two tabs/CAPTCHA error/503/lost successful response.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
expect(retryHeaders["Idempotency-Key"]).toBe(firstHeaders["Idempotency-Key"]);
expect(intentRequests).toHaveLength(1);
expect(signupRequestsAfterUnderageInput).toHaveLength(0);
```

- [ ] Step 2: `npm.cmd test -- src/api/client.test.ts src/features/guest/guestAttempt.test.ts`; owned Playwright `guest.spec.ts` -> expected no explicit-key support/entry fails.
- [ ] Step 3: Implement entry contract/disclosure/age check using existing Eligibility labels/rules, Turnstile adapter only after compatibility; single submit disables repeated action. On success validate session, set CSRF, navigate #/assistants. Each new attempt requires explicit CTA; registered session never overwritten.
- [ ] Step 4: Same commands ->PASS.
- [ ] Step 5: Owned Playwright `auth.spec.ts landing.spec.ts`; `npm.cmd run typecheck`; `npm.cmd test`.
- [ ] Step 6: Inspect key/cookie ownership and no token/age storage, no sensitive BroadcastChannel payload, CAPTCHA reset on definitive rejection only; ambiguous attempt explains waiting/retry safely.
- [ ] Step 7: Commit `feat(web): add explicit recoverable guest entry`.

**Acceptance:** No email/password; consent remains separate; no auto retry new identity. **Edge cases:** sessionStorage unavailable ->in-memory key/no reload recovery (safe explicit error); pending in another tab; disabled readiness midflow. **Rollback:** CTA off, active lifecycle still works. **Completion evidence:** identical replay keys/provider count and entry state screenshots.

### Task GE-09.2 — Expire private UI and add guest variants

**Objective:** Guest timer/permissions/copy reflect server state and private state cannot return after expiry. **Priority:** P1. **Dependencies:** GE-09.1.

**Architecture:** Abort registry and lifecycle epoch; remount private subtree by user/lifecycle, existing session context retained.

**Files:** Create `frontend/src/features/guest/{GuestStatus,GuestExpired}.tsx`, `useGuestLifecycle.ts`, `guestClock.ts`; Test `frontend/src/features/guest/guestClock.test.ts`, `frontend/tests/e2e/guest-expiry.spec.ts`, `frontend/tests/fullstack/guest-journey.spec.ts`; modify `frontend/src/features/real/{RealApp,Eligibility,AssistantGuide,AIData,Privacy,Voice}.tsx`, `social/useSocialSummary.ts`, `frontend/src/api/client.ts`, `frontend/src/api/stream.ts`.

**Interfaces:** Produces lifecycle hook above, `remainingGuestMs(expiresAt:string,serverTime:string,observedMonotonicMs:number,currentMonotonicMs:number):number` (clamp parsed deadline−serverTime−elapsed to≥0), and `ApiClient.onUnauthorized?: (error?:ApiError)=>void` (pass code, preserve REAUTH_REQUIRED distinction); `ApiClient.reset()` aborts registered in-flight controllers for old epoch as well as clears CSRF/intents. Event/audio callbacks check captured epoch and signal before setState.

- [ ] Step 1: Unit `guestClockDoesNotExtendOnRefreshOrWallClockChange` asserts sameT with server offset/monotonic elapsed. Browser “expires both tabs/offline at T”, “late fetch/voice/SSE callback cannot restore private UI”, “new trial fresh IDs and empty data”, “guest sends no social polling”; assert private draft/blob URL/feedback/tour state cleared.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
expect(
  remainingGuestMs(
    "2026-10-28T02:00:00Z",
    "2026-10-28T00:00:00Z",
    0,
    7_200_000,
  ),
).toBe(0);
await expect(
  page.getByRole("heading", { name: "L??t d?ng th? ?? k?t th?c" }),
).toBeVisible();
expect(latePrivateUpdates).toHaveLength(0);
```

- [ ] Step 2: `npm.cmd test -- src/features/guest/guestClock.test.ts`; owned Playwright `guest-expiry.spec.ts` -> expected expiry/cleanup failures.
- [ ] Step 3: Implement state matrix, timer/revalidation and cleanup: abort fetch/streams/recorder, stop tracks, revoke blob URLs, clear AIData/drafts/preferences/tour/attempt key, unmount private subtree. Quiet warning once; display minutes and aria-live only warning/end. Locked /connect and guessed /messages/chat show same registered explanation without API calls.
- [ ] Step 4: Same commands ->PASS; feedback form uses lifecycle signal when added later.
- [ ] Step 5: Backend harness `uv run --locked python ../scripts/test_fullstack.py guest-journey.spec.ts --reporter=list`; frontend type/unit/build and owned `real.spec.ts auth.spec.ts states.spec.ts`.
- [ ] Step 6: Check all copy variants including RealApp retentionLabel/historyStatus, voice preview, export/end confirmation. Registration explicitly confirms loss, calls end, then #/login?mode=signup; cancellation leaves active guest unchanged. Never transfer data/consents.
- [ ] Step 7: Commit `feat(web): add deadline-aware guest experience`.

**Acceptance:** Refresh/reopen retained cookie preservesT; no old callback/state reappears; five bots available when consent/budget permit; registered behavior unchanged. **Edge cases:** DB/auth 503 vs expired 401, expired unknown cookie, no BroadcastChannel/Web Locks, cleanup pending with no auth, browser sleep/back/forward cache. **Rollback:** keep expiry handler and guest-aware UI with entry disabled. **Completion evidence:** multi-context/tab fullstack output and narrow/desktop keyboard/state evidence.
