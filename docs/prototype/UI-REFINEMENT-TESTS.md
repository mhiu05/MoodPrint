# UI refinement verification

Date: 2026-11-07. Browser: local headless Chromium through Playwright. Application screenshots use port 5179; the unchanged E2E config launches Vite on 5178. No real-device testing claimed.

## Commands and results

Run from `frontend/` using `npm.cmd` on this Windows machine (PowerShell blocks npm.ps1).

| Command | Result |
|---|---|
| npm.cmd run typecheck | PASS, no TypeScript errors |
| npm.cmd run lint | PASS, no ESLint errors |
| npm.cmd run build | PASS, production assets generated locally |
| npm.cmd test | PASS, **54 tests in 13 files** |
| npm.cmd run test:e2e | PASS, **13 Chromium tests**, approximately 1.9 minutes |
| npm.cmd run check:boundaries | PASS, no detected credentials, application networking/microphone APIs or live-service dependencies |
| node scripts/refinement-screenshots.mjs before | 14 actual baseline screenshots |
| node scripts/refinement-screenshots.mjs after | 18 final screenshots including processing and inline analysis |

The first sandbox test attempt could not read esbuild's parent directory. The tests were subsequently run with the approved local process permissions; this was an environment startup failure, not an application failure. Terminal NO_COLOR/FORCE_COLOR messages are runner environment warnings, not browser console errors.

## Regression evidence

- Baseline: 53 tests / 13 files passed before implementation.
- Added local message timestamp test: failed because `createdAt` did not exist; passed after implementation. Old fixture data remains unchanged.
- Added processing header test: failed at 320px with idle height 67.39px versus processing height 92.98px. Stable visible demo status fixes this; the final E2E passes.
- An existing manual-reading test initially failed because it counted the streaming bubble before the reply finished and attempted another send while busy. It now explicitly waits for `.ai-stream` to disappear in addition to checking message count. The assertion that new incoming content does not move a reader from scrollTop=0 remains intact.
- Existing retry test verifies the next draft remains editable during errors and is retained through retry. IME and Shift+Enter checks remain.
- Added inline analysis test verifies 0/8 confirmed-source disclosure, emergency access, overflow and composer bounds at every required width.

## Responsive coverage

Widths: **320, 360, 375, 390, 430, 768, 1024, 1440**.

| Surface/state | Checks |
|---|---|
| Four Welcome steps | 32 width/step combinations; visible h1 and Skip, flower parts within art bounds, Next reachable, no horizontal overflow |
| Auth | Login/register controls and register alias available across width matrix; no horizontal overflow; mock persona/login/guard journeys |
| Ordinary workspace | Home, AI, cases, wizard, timeline, plan, roleplay, Knowledge, article, Support, prepare, urgent, Admin: 14 routes x 8 widths = 112 visits |
| Chat empty | h1, composer and route render, no horizontal overflow, no bottom nav/sidebar |
| Active chat and inline evidence | All 8 widths at 640px height; source card, direct urgent shortcut, no horizontal overflow, composer bottom <=640px |
| Short chat | All 8 widths at 480px height; multiline composer remains within viewport, document height does not exceed viewport |
| Keyboard simulation | 390px width, visualViewport reduced from 844px to 420px while focused; keyboard flag and composer bounds checked |
| Short Welcome | 320x480; Next and Back function with natural scrolling |
| Processing | 320px header remains same height; actual mock lifecycle visible with identity intact |

Responsive tests assert no browser page errors, console errors or external requests in their coverage. The primary journeys also record page errors and external traffic. No external calls were detected. Safe-area behavior is implemented with CSS environment variables but not certified on physical notched devices.

## Journeys exercised

| Journey | Evidence |
|---|---|
| Onboarding -> mock account -> Home | entry-admin.spec.ts; four steps, Skip path in journey.spec.ts |
| Home -> Chat -> multiple messages | journey.spec.ts at 390 and 1440; direct AI Hub/tab navigation in entry/responsive tests |
| Scenario/history | ui-refinement.spec.ts: 30 options, history dialog, focus return, all 12 scripts advance through three turns |
| Chat -> eight images -> review -> case | journey.spec.ts: eight evidence rows, create disabled until confirmation, six confirmed timeline entries, case confirmation |
| Case -> Action Plan -> progress | journey.spec.ts; existing component/state suites exercise Home synchronization |
| Roleplay -> feedback | full journeys: three turns, feedback and selected transcript handoff |
| Support -> prepare -> mock submission | preview, explicit simulation checkbox, save and no-send status |
| Profile after header removal | Support Cài đặt link reaches /settings |
| Emergency support | Public /support/urgent and tel:111; chat shortcut visible at all widths |
| Admin isolation | 48 independent reports, filters and local status updates, no student nav/data mixing |
| Draft continuity | Back to Hub, recent session, reload, menus, history and roleplay navigation preserve draft |
| Manual scroll | Reader stays at top as response completes; latest-message action returns to bottom |

## Visual and accessibility inspection

Opened all 11 reference PNGs visually. Inspected actual baseline mobile Welcome, Auth, Home, AI Hub, empty and active chat. Inspected final mobile Auth, empty chat, conversation, processing, source card, Support, 320px inline analysis and simulated keyboard captures, plus desktop Welcome, Auth, empty chat and AI Hub. Checked hierarchy, density, green identity, bubble widths, text wrapping and composer position. Screenshot generation alone was not treated as visual review.

Evidence directory: [screenshots/ui-refinement](screenshots/ui-refinement/). Baseline and final are explicitly separated. Additional inline-analysis screenshots cover all eight widths. Browser-generated screenshots for existing case/plan/roleplay/support/admin coverage also remain in `screenshots/`.

Accessible behavior covered: semantic headings and controls, labeled composer, IME-safe input, Shift+Enter, native dialog Escape/focus restoration, visible focus in keyboard capture, minimum 44px chat controls and reduced-motion fallback. No fresh axe audit, screen-reader session, real keyboard hardware or WCAG certification is claimed in this refinement. Historical a11y-evidence.json belongs to the prior implementation run.

## Limits

A separate read-only code review found no actionable important bugs in the modified chat/auth/contracts and regression tests. It confirmed timestamp compatibility, preservation of next drafts during reply completion, IME guards, confirmed-source progress and 320px emergency access. No extra test execution was claimed by that reviewer.

No Safari/Firefox, physical iOS/Android, assistive-technology or student usability testing. visualViewport manipulation models a keyboard; it does not prove real mobile keyboard behavior. AI/OCR/voice/auth/submission remain deterministic local simulations. Free text does not receive real understanding. No production service, deployment or cloud checks were needed or performed.
