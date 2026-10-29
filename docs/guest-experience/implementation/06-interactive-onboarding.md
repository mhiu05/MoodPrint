# Interactive Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optional short guidance that can be skipped/replayed and never changes data or permissions.

**Architecture:** Route-aware controller owns navigation/readiness/state; a lazy Driver.js adapter owns spotlight geometry only after compatibility proof. Accessible inline step list remains a fallback.

**Tech Stack:** React 19 StrictMode, existing HashRouter/GSAP/native Dialog/motion policy; conditional pinned Driver.js 1.10.2; Vitest/Playwright.

**Spec:** [Approved onboarding design §§4–6](../03-landing-onboarding-design.md), [guest UI boundary](04-public-landing-and-guest-ui.md), [index constraints](00-implementation-index.md#global-constraints).

## Global Constraints

PRODUCT_TOUR_ENABLED=false until proof; no package/lockfile change before gate. Default no automatic overlay. Four initial steps; guest never visits social. No consent toggles, message sending, journal saving, memory approval or active emotional-chat/microphone interruption. Cleanup at unmount/end/T. No unrelated UI redesign.

## Review Focus

1. StrictMode repeated mount/start → exactly one overlay/listener set (GE-13.1/13.2).
2. Hidden/absent target or failed route resource → bounded fallback, no(0,0) spotlight (GE-13.2).
3. Native top-layer dialog/GSAP/route heading focus → one focus owner (GE-13.1/13.2).
4. Soft keyboard/200% text/reduced motion → visible controls and correct geometry (GE-13.1).
5. Guest expires or AI/voice starts during readiness wait → abort/destroy, never late overlay (GE-13.2).

## Option selection and compatibility gate

| Option                       | Fit                                                                      | Decision                                                                                            |
| ---------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Driver.js imperative adapter | Small framework-independent geometry; app owns route state and lifecycle | **Selected conditional candidate 1.10.2/MIT** from audit; exact package/type/runtime proof required |
| React Joyride                | React wrapper, controlled steps; more peer/provider/adapter surface      | Fallback evaluation only if Driver fails for a documented reason; no simultaneous dependency        |
| Reactour                     | React context/provider masking/focus                                     | Viable but no benefit shown for current architecture                                                |
| Custom overlay               | Full geometry/focus/clipping responsibility                              | Avoid; use simple inline guide instead if spotlight cannot pass                                     |

Official [configuration](https://driverjs.com/docs/configuration) and [repository](https://github.com/kamranahmedse/driver.js) are reference sources; current docs may describe features newer than 1.10.2. Do not use undocumented-for-pinned-release options. No runtime compatibility/a 11y claim has been established by planning.

Before adding a dependency, obtain exact tarball/version/license/integrity using `npm.cmd view driver.js@1.10.2 version license dist.integrity dist.tarball --json`. Inspect package contents/scripts/license. Use an owned OS-temp extraction for the spike (`npm.cmd pack driver.js@1.10.2 --ignore-scripts --pack-destination "$env:TEMP"`), inspect archive paths before extracting to a unique temp directory. No manifest/lockfile changes for spike. Serve the pinned bundle/CSS as same-origin test fixture URLs through Playwright route fulfillment, never a CDN or inline-script bypass. Exercise **actual app routes/StrictMode/headers**, not just an empty HTML sandbox. After all technical checks pass, add exactly 1.10.2 with `npm.cmd install --save-exact driver.js@1.10.2 --ignore-scripts`, review lock/audit/license. Review pins at implementation time if unavailable/vulnerable; record a justified replacement and rerun gate.

Gate requires: React 19/StrictMode repeated mounts; Router 7 route transitions/back; native Dialog and route focus; GSAP layout settle; actual Caddy and FastAPI CSP; keyboard Next/Back/Skip/Finish/Escape and focus return; SR title/description/step count; no inert/aria-hidden ancestor hiding active popover;320/390/768/1440 widths/landscape/soft keyboard/200%text; reduced-motion no tween/smooth scroll; resize/scroll cleanup; no app mutation. Automated axe does not replace manual NVDA/VoiceOver.

If technical proof fails, remove owned spike artifacts, keep dependency absent/flag off, expose inline four-step guidance/replay, record exact failed criterion. Do not silently mark optional spotlight accepted; release can explicitly defer it. If only manualSR device access is unavailable, record PARTIAL and keep public flag off pending review.

## Controller/state/target contracts

Create `frontend/src/features/onboarding/tourSteps.ts` with `getTourSteps(session:SessionView,includeMatching:boolean=false):TourStep[]`:

`TourStep={id:'assistants'|'mood'|'memory'|'privacy'|'matching';route:string;target:string;title:string;description:string;isApplicable:(session:SessionView)=>boolean}`.

| Step              | Route / stable target                       | Static teaching copy                                                                                                                  |
| ----------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| assistants        | /assistants / [data-tour='assistants-list'] | “Chọn trợ lý hợp với điều bạn muốn làm hôm nay. Bạn có thể đổi bất cứ lúc nào.”                                                       |
| mood              | /self / [data-tour='mood-entry']            | “Ghi lại cảm xúc của bạn. Ghi chú là tùy chọn và vẫn là thông tin riêng.”                                                             |
| memory            | /memory / [data-tour='memory-intro']        | “Trợ lý chỉ ghi nhớ khi bạn duyệt. Bạn có thể sửa hoặc xóa sau.” Use intro/empty state, no private values read aloud.                 |
| privacy           | /settings / [data-tour='privacy-controls']  | “Bạn chọn quyền xử lý dữ liệu và có thể rút lại bất cứ lúc nào.” Guest adds “Dữ liệu của lượt thử không mở lại được sau khi hết giờ.” |
| matching optional | /connect / [data-tour='matching-intro']     | Extra opt-in registered adult introduction; explanation/preview only. Never enable MATCH. Excluded for guest/teen/ineligible.         |

Targets live in current RealApp Assistants/Moods/ApprovedMemories/Settings and social Discovery; add attributes on stable heading/intro regions, not dynamic user data. Controller has no arbitrary selector from server.

`TourState={version:'tour-v1';status:'idle'|'waiting'|'showing'|'skipped'|'completed';stepId:TourStep['id']|null;promptDismissed:boolean}`.

`TourAdapter={show:(target:HTMLElement,step:TourStep,index:number,total:number)=>void;refresh:()=>void;destroy:()=>void}` (in tourAdapter.ts, actual library in driverAdapter.ts). Define `TourCallbacks={next:()=>void;back:()=>void;skip:()=>void;finish:()=>void}` there; `createDriverAdapter(callbacks:TourCallbacks,motion:{reduced:boolean}):TourAdapter` wires library controls to controller, never its own route advancement.

`waitForTourTarget(selector:string,signal:AbortSignal,timeoutMs:number=3000):Promise<HTMLElement|null>`: route settled first, visible geometry for 2 animation frames, bounded Mutation/Resize observer, cancel immediately. Never await forever/smooth-scroll under reduced motion.

`TourController({session,activity}:{session:SessionView;activity:TourActivity})` inside HashRouter, consumes useLocation/useNavigate/useMotionPolicy. `TourActivity={aiBusy:boolean;voiceBusy:boolean;hasDraft:boolean}` from small `tourActivity.ts` registry; `setTourBlocker(id:string,kind:'ai'|'voice'|'draft',active:boolean):void` and `clearTourBlockers():void`, subscribe via useSyncExternalStore. Existing chat/Voice explicitly register/cleanup their states; do not infer sensitive content from DOM. No content in registry.

Start only explicit “Xem hướng dẫn”; if draft/busy/dialog open show “Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.” No route change/destruction of draft. When active, any new blocker/dialog ->destroy/suspend (no automatic restart); user can replay. Observe native dialog opening during tour and destroy before taking focus; z-index is not a solution to top layer.

goToStep: increment cancellation generation, abort previous wait, navigate exact route, await readiness≤3s, confirm active session/epoch and no blocker, settle geometry, show. Missing first critical target ->destroy and “Chưa thể mở hướng dẫn ở màn hình này. Thử lại sau.” Later missing target ->skip to next once, announce inline status; if none remain finish. Browser Back or unrelated route change cancels tour, no forced navigation loop. Back uses previous applicable step; close/Escape/Skip always available; backdrop never advances.

Controls: “Tiếp”, “Quay lại”, “Bỏ qua”, “Hoàn tất”, “Bước 2/4”. Popover role/title/description association and one focus owner; keyboard focus remains on visible tour controls, highlighted region informational. Restore focus to connected visible launcher or destination heading. SR-accessible ordered step list supports same content without spotlight.

State hook: `useTourState(session:SessionView):{state:TourState;start:()=>void;skip:()=>void;finish:()=>void;reset:()=>void;setStep:(id:TourStep['id'])=>void}`. Guest RAM scoped to lifecycle, clear at T/end; registered local preference key moodprint:tour:tour-v 1:registered:<userId>, no private content, replay/reset always possible. No persistent guest UUID. Hide automatic invitation after dismiss; no automatic overlay after expiry/restart. Cleanup adapter, observers, timers, listeners, body scroll/inert state and focus restoration on unmount/StrictMode/end/T; no setState after aborted generation.

### Task GE-13.1 — Prove the spotlight candidate

**Objective:** Decide dependency by actual app evidence. **Priority:** P2. **Dependencies:** GE-09.2.

**Architecture:** Isolated temporary package proof; no application dependency before gate.

**Files:** Create `frontend/tests/e2e/onboarding-compatibility.spec.ts`, `frontend/src/features/onboarding/tourAdapter.ts`, `tourSteps.ts` (TourStep type only, before adapter imports it); create `docs/guest-experience/implementation/evidence/tour-compatibility.md`; modify `frontend/package.json`, `package-lock.json` **only after pass**.

**Interfaces:** Produces accepted candidate/integrity/API adapter constraints or explicit deferred spotlight. Test fixture loads package asset from owned temp path supplied `MOODPRINT_TOUR_SPIKE_DIR`, never fetched from production.

- [ ] Step 1: Add named tests “one overlay after StrictMode remount”, “Escape/focus restoration”, “dialog collision cleans overlay”, “reduced motion and narrow viewport”, “real CSP has no blocked tour resources”; each asserts focus/overlay count/cleanup and zero mutation requests.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
await expect(page.locator(".driver-popover")).toHaveCount(1);
await page.keyboard.press("Escape");
await expect(page.locator(".driver-popover")).toHaveCount(0);
```

- [ ] Step 2: `npm.cmd exec -- playwright test --config playwright.owned.config.ts onboarding-compatibility.spec.ts` without package fixture ->meaningful unavailable adapter failure; do not let a missing fixture count as successful proof.
- [ ] Step 3: Inspect pinned temp tarball, implement test-only fixture/adapter spike, run matrix above under both serving modes; record manualSR/soft-keyboard outcomes or explicit blocked items.
- [ ] Step 4: Same command with inspected fixture ->PASS only observed technical cases. If required technical case fails, keep library absent/flag off and record deferred result.
- [ ] Step 5: On technical pass only, install pinned dependency, run `npm.cmd audit --audit-level=low`, `npm.cmd run typecheck`, `npm.cmd run build`; no threshold bypass. Confirm actual distribution API matches adapter.
- [ ] Step 6: Review license/CSP/scripts, screenshot/focus evidence and no duplicate GSAP ownership.
- [ ] Step 7: Commit `test(onboarding): gate spotlight compatibility` (include dependency only when justified).

**Acceptance:** Conditional selection resolved with evidence, no falsely certified a 11y. **Edge cases:** library release mismatch, CSP denial, absent SR device, package advisory. **Rollback:** remove owned spike/dependency if unaccepted, keep inline guide. **Completion evidence:** exact pinned package/integrity, commands/browser matrix/manual gaps.

### Task GE-13.2 — Implement short route-aware replayable tour

**Objective:** Teach four core actions with bounded navigation/cleanup. **Priority:** P2. **Dependencies:** GE-13.1, GE-12.2.

**Architecture:** App owns state/route/deadline, library only geometry; inline guide if spotlight unaccepted.

**Files:** Create `frontend/src/features/onboarding/{TourController.tsx,useTourState.ts,tourActivity.ts,waitForTourTarget.ts,driverAdapter.ts,onboarding.css}` (driverAdapter only accepted candidate); extend `frontend/src/features/onboarding/tourSteps.ts` from GE-13.1 with actual steps/getTourSteps; Test `frontend/src/features/onboarding/tourSteps.test.ts`, `frontend/tests/e2e/onboarding.spec.ts`; modify `frontend/src/features/real/RealApp.tsx`, `Voice.tsx`, `social/Discovery.tsx`, `frontend/src/features/guest/useGuestLifecycle.ts`.

**Interfaces:** Produces exact contracts above. Consume SessionView/deadline epoch/readiness and accepted adapter only; no new backend endpoint.

- [ ] Step 1: Unit “guest has 4 steps/no matching”, “registered teen 4/adult optional 5”, “skip/finish/replay/version reset”. Browser “Next/Back/Skip/Finish/Escape”, “missing target resolves≤3s”, “browser Back cancels”, “expiry/blocker/unmount removes overlay”, “draft start refuses navigation”; assert no POST/PUT/PATCH/DELETE from tour.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
expect(getTourSteps(guestSession)).toHaveLength(4);
expect(
  getTourSteps(guestSession, true).some((step) => step.id === "matching"),
).toBe(false);
expect(tourMutationRequests).toHaveLength(0);
```

- [ ] Step 2: `npm.cmd test -- src/features/onboarding/tourSteps.test.ts`; owned Playwright `onboarding.spec.ts` -> missing controller/targets/state fails.
- [ ] Step 3: Implement controller/targets/state/adapter and inline guide, with motion/focus/readiness rules above. Lazy-load code/CSS only on explicit guide launch and accepted public flag. Settings replay remains discoverable.
- [ ] Step 4: Same commands ->PASS at 320/390/768/1440/landscape/200%text and reduced motion; no late overlay after T.
- [ ] Step 5: Owned `guest-expiry.spec.ts real.spec.ts auth.spec.ts`; frontend typecheck/unit/build; fullstack guest-experience scenario inGE-14.1.
- [ ] Step 6: Review all cleanup resources, native Dialog/GSAP focus, keyboard/SR note count and privacy of state. Manual unavailable remains PARTIAL/public spotlightoff.
- [ ] Step 7: Commit `feat(onboarding): add optional route-aware guidance`.

**Acceptance:** Guidance optional/replayable/mutation-free, no guest social step/focus trap, bounded missing-target fallback. **Edge cases:** target late/hidden, auth 503, navigation error, resizing soft keyboard, second start/tab, active recording. **Rollback:** PRODUCT_TOUR_ENABLED=false; remove overlay immediately, inline guidance remains. **Completion evidence:** matrix, focus/mutation/cleanup assertions, manual gaps and bundle diff.
