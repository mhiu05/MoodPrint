# Natural Agent Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement the approved Grok-inspired AI chat surface with an inline working orb and one send/stop control.

**Architecture:** Preserve the existing run lifecycle and transcript metadata. Move AIActivityStatus into the transcript, keep cancellation ownership in ConversationBody, and scope the replacement visual tokens to .bot-conversation.ai-conversation so human chat and the rest of the application retain their styles.

**Tech Stack:** React 19, TypeScript, CSS, existing GSAP/@gsap/react, Thinking Orbs, Playwright, Vitest.

**Spec:** docs/superpowers/specs/2026-10-30-natural-agent-chat-design.md

## Global Constraints

- Do not edit .gitignore; preserve all pre-existing uncommitted changes.
- AI chat routes only; no backend/API/dependency changes.
- Stop remains a server-confirmed cancellation request, never pause/resume.
- Keep 44px touch targets, 16px message/input text, IME and draft semantics.
- User approved immediate implementation; execute inline without another plan approval round.

## Review Focus

- Empty draft during accepted run must still allow cancellation.
- Typing a draft while waiting must preserve it through cancellation and never submit it via the pause button.
- Read-only transition during an accepted run must retain one accessible stop action.
- Moving status into the log must not duplicate live announcements or force-scroll someone reading history.
- Responsive multiline input and voice controls must not clip at 360px or 666px.

## Task 1: Composer and status behavior

**Files:** RealApp.tsx, AIActivityStatus.tsx, aiActivityView.ts in frontend/src/features/real; frontend/tests/e2e/ux-redesign.spec.ts; relevant existing status-label tests.

**Interfaces:** Preserve AIActivityView. AIActivityStatus accepts onStop only for read-only fallback. ConversationBody derives the composer action from existing run/sync/stopRequested state.

- [x] Add regression tests for one composer stop action, empty-draft cancellation, draft preservation, duplicate-stop prevention, cancellation failure retry, read-only fallback and restored send action.
- [x] Run the new tests and confirm expected failures before editing product code.
- [x] Move status to the end of transcript with one polite live region; keep fallback cancellation in read-only state.
- [x] Reuse one button, type button during accepted run and submit when idle; pause icon/title/accessible label reflect the existing cancel lifecycle.
- [x] Use accepted label “Đang trả lời…” and update lifecycle assertions without weakening race/ownership tests.
- [x] Run AI activity and new conversation browser tests to confirm cancellation remains server-confirmed.

## Task 2: Replacement chat surface

**Files:** frontend/src/features/real/agent-chat.css (new scoped stylesheet); scoped header/introduction markup in RealApp.tsx; AIActivityStatus.tsx for GSAP cleanup.

**Interfaces:** Existing message, date, copy, voice, quick-reply and information-panel class contracts remain available.

- [x] Scope neutral tokens and layout under .bot-conversation.ai-conversation; white conversation, unframed assistant replies, soft-gray self messages, compact header and circular main action.
- [x] Hide introduction after messages exist; keep existing empty-state guidance. Restyle single-link cards inline.
- [x] Place status with message content and preserve static/reduced-motion/import-failure behavior. Keep status entry animation under 4px/160ms, no delayed content.
- [x] Capture and inspect synthetic desktop, 390px, 666px and narrow/multiline states; use existing accessibility checks, not tests for cosmetic constants.

## Task 3: Verify and document

**Files:** DESIGN.md, .impeccable/design.json, .impeccable/surfaces/agent-chat.md; this plan and progress record.

- [x] Run npm test, npm run typecheck and npm run build from frontend.
- [x] Run relevant chat/history/voice/metadata/motion browser tests; record exact failures/skips.
- [x] Run Impeccable detector on changed UI files once and fix mechanical findings.
- [x] Request fresh code and visual review with screenshots and approved design; resolve material findings and verify affected checks.
- [x] Record final scoped tokens and surface behavior; leave user changes uncommitted for review.

## Execution record

- Baseline: typecheck passed; 10 related unit tests passed; 17 activity/metadata/info browser tests passed before implementation.
- Ruling: user-pinned Grok direction overrides concept seed candidate 5 (seed:26d0e8a6f7dcc1ea). No new style-selection round; white/gray surface and send/pause behavior are approved.
- Ruling: retain existing workspace to preserve and build on uncommitted metadata changes. No automated git commit or .gitignore-changing scratch setup.

- Task 1: complete. New send/stop, failure and read-only tests failed as expected before implementation, then passed.
- Task 2: complete. Eight screenshots reviewed across 360/390/666/1440px. Scope isolation and multiline resize findings each received a failing regression before correction.
- Task 3: complete. 107 unit tests and build passed; final affected browser run 122 passed with 3 independently confirmed pre-existing failures explicitly excluded. Detector returned no findings. See the linked verification report for exact exclusions.
- Ruling: put replacement CSS in agent-chat.css instead of extending shared me2we.css, and require .ai-conversation because human chat also uses .bot-conversation. Keeps the approved AI-only scope and preserves user metadata styles.
- Ruling: keep uncommitted changes reviewable in the existing feature branch; no push, merge or deployment. Archive temporary evidence under the already ignored docs/ux-redesign/evidence directory without editing .gitignore.
- Documentation handoff wrote DESIGN.md and the surface brief before its usage limit interrupted it. Parent completed and checked the schemaVersion 2 sidecar and corrected evidence links.
- Verification: docs/superpowers/specs/2026-10-30-natural-agent-chat-verification.md.