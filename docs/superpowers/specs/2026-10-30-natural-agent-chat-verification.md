# AI chat redesign — verification

Approved design: [natural agent chat](2026-10-30-natural-agent-chat-design.md). Local implementation only; no deployment or commit performed.

## Result

- `npm test`: **107 passed**, 22 test files.
- `npm run build`: **passed**, including TypeScript checking and Vite production build.
- Browser suite (`ux-redesign.spec.ts`, `motion.spec.ts`, `chat-history.spec.ts`, `merge-readiness.spec.ts`): **122 passed** in the final run, with the three independently confirmed pre-existing failures below explicitly excluded via `--grep-invert`.
- Full earlier run: **121 passed, 3 failed** before the last scope/resize regression was added. Those same three failures were reproduced against a disposable archive of unchanged HEAD `13ad3263498c0712cfc43012d451587f6025d27b`, on a separate local port.
- Impeccable detector on `agent-chat.css`, `AIActivityStatus.tsx`, `RealApp.tsx`: empty findings. Automated accessibility checks at phone/desktop and 200% text passed within the browser suite.
- Code review: scope leak from shared human-chat class fixed and covered by a red→green isolation regression; no remaining reported code blockers.
- Visual review: all eight captures inspected. The one material finding (working status clipped at 360px when composer grows) was reproduced with a failing regression, fixed with conditional resize anchoring, recaptured and scored resolved; `ship` verdict covers that fix list.

## Pre-existing browser failures

These remain unchanged and are not reported as passing:

1. `with AI processing off a pending proposal points to an explicit Send, not to Settings`: expectation conflicts with existing eligible-user proposal behavior.
2. `with approved memory off the page explains that approving a proposal is the way back`: expected text is absent in existing Memory UI.
3. `body text is 16px and persona descriptions are readable without truncation at every width`: existing roster test queries a missing `.bot-row-text small` element.

## Coverage and evidence

Synthetic fixture data; no real model/provider or production writes. Covered send/accepted/cancel lifecycle, cancellation failure and races, draft preservation, history, metadata copy/hover/touch/focus, voice insertion, reduced motion, failed orb import, hidden tabs, read-only stop fallback, human-chat style isolation and reading old messages while the composer resizes.

Inspected 360px, 390px, 666px and 1440px. Phone and desktop working states are `working-390.png` and `working-1440.png` under the ignored `docs/ux-redesign/evidence/natural-agent-chat-2026-10-30/captures/agent-chat/` directory. `.gitignore` was not edited.

Browser/DOM checks do not establish actual speech output for every screen-reader/browser combination. The Grok interactive demo was blocked by Cloudflare; this is the approved interpreted design rather than a pixel reproduction.
