# MoodPrint prototype — independent code review

> Final verification by the primary implementer, 07/11/2026: the initial findings below are preserved as review history. Their earlier pending statuses are superseded by the closure matrix at the end. The independent reviewer did not run the final browser suite; the root agent ran it and retained the evidence.

Reviewed 07/11/2026 against docs/prototype/01–08 and IMPLEMENTATION-EXECUTION.md. Scope: current frontend source, state ownership, routing, cross-feature handoffs, demo semantics, and code-level accessibility. Read-only review; only this report was written. Browser and full test execution are owned by the root agent and were not repeated. Findings below include reproducible code paths; statuses distinguish code updates from verification.

## Important findings

### R1 — Persona switches exposed another persona's personal lists
- Location: frontend/src/app/store.ts (original lines 15–25; revised lines 6–8, 24–25, 32).
- Reproduction: sign in as An; add a trusted person, bookmark/read an article; logout; sign in as Minh. The prior implementation reused global trustedPeople/bookmarks/readIds.
- Impact: the UI calls the list private while other mock accounts see its values. Cases themselves were correctly filtered by owner.
- Fix direction: scope these values by persona, including persistence and restoration.
- Status: root implemented a per-persona scope map and reports red→green regression tests. Source reviewed; browser verification pending.

### R2 — Reset left recoverable case and plan drafts behind
- Location: frontend/src/app/store.ts reset (revised lines 8, 25); frontend/src/features/incidents/wizard.tsx:14–15; frontend/src/features/action-plans/index.tsx:34–37.
- Reproduction: write a case or edit a plan without explicit saving; leave; reset demo in Settings; sign in as the same persona and reopen the form. sessionStorage restored the pre-reset content.
- Impact: contradicts the reset confirmation that all demo changes will be removed.
- Fix direction: remove only the app's case/plan draft keys during reset.
- Status: root implemented targeted removal and reports regression tests passing. Source reviewed; browser verification pending.

### R3 — Report edits could leak between School Admin reports
- Location: frontend/src/features/school-admin/index.tsx (SchoolPage local notes/newStatus state, originally line 11).
- Reproduction: open SCHOOL-DEMO-001; change notes/status; go back to reports; open SCHOOL-DEMO-002. The unkeyed same component retained 001's local state and saving wrote it into 002.
- Impact: corrupts the otherwise correctly independent synthetic report dataset and associated aggregates.
- Fix direction: key/reset editor state by report ID.
- Status: root reports SchoolView now keyed by report ID. Source recheck/interaction verification pending.

### R4 — Reload during analysis could leave it permanently processing
- Location: frontend/src/features/ai/analysis.tsx (run and processing rendering; revised around lines 30, 43–46, 66).
- Reproduction: start opening a fixture analysis, reload during the 800 ms pending interval. The persisted processing state had no active task and rendered neither retry nor recovery.
- Impact: blocks the flagship analysis→confirmation→case flow.
- Fix direction: distinguish an active local task from a persisted interrupted task and expose retry while retaining input.
- Status: AI worker updated source with running state and interrupted-run retry. Narrow regression verification pending.

### R5 — Confirmed correction on near-duplicate image was discarded
- Location: frontend/src/features/ai/analysis-model.ts:22–31 (original implementation).
- Reproduction: confirm MEDIA-07; change MEDIA-08 to different text and confirm it; create the case. The original merge checked only the MEDIA-08/07 ID suffix and retained only 07's description.
- Impact: silently loses a user-confirmed correction and misrepresents the review result.
- Fix direction: merge equivalent content only; preserve distinct corrections with uncertainty metadata.
- Status: AI worker has a regression test for distinct corrections and is addressing the implementation.

### R6 — Support settings regenerated and destroyed the user's message
- Location: frontend/src/features/support/index.tsx:63–75, 86 (original composer initialization and update).
- Reproduction A: save a custom preview; reopen it; change recipient or identity mode. values.detail was initialized from the case summary/roleplay rather than saved content, and update(..., true) replaced the custom preview.
- Reproduction B: from case-linked roleplay, select one transcript fragment for Support; change recipient. Initial preview showed only selected lines, but regeneration used the entire case summary because initialCase.summary preceded fromRoleplay.
- Impact: loses edits and expands content beyond the fragment the user chose to carry forward.
- Fix direction: preserve custom preview, prioritize selected fragments, and require explicit regeneration/replacement rather than doing so from unrelated setting changes.
- Status: support worker assigned; verification pending.

### R7 — Unsaved Support text was lost on navigation without warning
- Location: frontend/src/features/support/index.tsx:62–75, 86.
- Reproduction: type an original message without saving; select Home/another tab or browser Back; reopen the composer. Text was local useState only and disappeared without confirmation.
- Impact: violates IA §4.1's unfinished-form guard and loses a potentially difficult-to-recreate message.
- Fix direction: add a navigation guard with save/leave/continue or explicit safe draft recovery, including reload handling.
- Status: reported to root/support worker; pending.

### R8 — Recovered plan draft can overwrite newer Home checklist updates
- Location: frontend/src/features/action-plans/index.tsx:34–37, 52–53, 63; frontend/src/features/home/index.tsx (Home checkbox putPlan).
- Reproduction: edit the plan goal without saving; navigate Home; toggle a plan item; return to plan. The sessionStorage draft is always preferred over the newer canonical plan and displays the previous checkbox value. Saving the goal writes that older checklist over Home's update.
- Impact: violates the canonical shared plan requirement and silently undoes a completed step.
- Fix direction: store a draft base revision and reconcile updates, or offer a clear conflict choice. A draft should not blindly win over newer canonical changes.
- Status: reported to root; pending.

### R9 — Existing wizard draft replaced incoming Chat story but kept its new chat link
- Location: frontend/src/features/incidents/wizard.tsx:31–34, 60.
- Reproduction: leave unrelated new-case draft A unfinished; open Chat B; confirm creating a case from B. readDraft overwrites B's incoming prefill with A. Saving still assigns B's prefill.linkedChatIds, yielding A's story linked to B.
- Impact: loses the confirmed handoff and creates an incorrect source relationship.
- Fix direction: explicitly choose resume existing draft vs start from imported story, or assign distinct draft identities to separate handoffs.
- Status: reported to root; pending.

### R10 — Knowledge→Chat source context disappeared after the first message
- Location: frontend/src/features/knowledge/index.tsx:54, 58; frontend/src/features/ai/chat.tsx:48, 52–55, 84.
- Reproduction: click Hỏi AI về bài này from any article; send the first message. send navigates to /ai/chat/:id without preserving query metadata, and ChatSession had no article/source context fields.
- Impact: the "context preserved" notice was only valid on the entry URL; reopening the session loses source attribution and context.
- Fix direction: persist article/source metadata on ChatSession and display useful article/source links in the conversation.
- Status: AI worker assigned; pending.

## Minor findings

### R11 — Knowledge filter deep links did not apply any filters (P2)
- Location: frontend/src/features/knowledge/index.tsx:20–25; frontend/src/features/home/index.tsx (online/communication topic links); frontend/src/features/profile/index.tsx (no-results demo link).
- Reproduction: use either Home learning card or Settings's "Thử tìm kiếm không có kết quả." KnowledgeHub initialized filters to empty strings and did not read URL params, so all articles were shown.
- Fix direction: parse supported query params with topic aliases and preserve updates through navigation.
- Status: support/knowledge worker assigned; pending.

### R12 — Shared Field help is not associated with custom textarea/select children (P2, accessibility)
- Location: frontend/src/components/ui/index.tsx:11; e.g. frontend/src/features/incidents/wizard.tsx (case-story Field).
- Cause: Field sets aria-describedby/aria-invalid only on its own generated input. When children is supplied, the hint/error renders visually but is not attached to the child control.
- Impact: a screen reader focused on the story textarea does not receive the adjacent validation message or hint through the shared field contract. case-story manually sets invalid but still lacks describedby.
- Fix direction: pass the generated help ID to controls (render prop/context or cloning a single typed control) and move focus to the invalid field on attempted completion.
- Status: pending; no browser/screen-reader claim made.

## Positive findings and review limits

- Public urgent route exposes tel:111 without authentication and keeps the user in control of the external action.
- Case detail/list/wizard and AI records consistently check current owner IDs on reads.
- School store imports only its own synthetic seed, never student cases. All 48 reports, KPI totals, category totals and monthly totals derive from one filtered dataset.
- Demo notices consistently distinguish local saving from real sending, school intake, OCR/AI, voice recording and absolute anonymity.
- Native dialogs, labels, landmarks, visible focus CSS, explicit source limits, and reduced-motion paths provide a sound baseline. No general screen-reader conformance claim is made from source alone.
- No browser session, full test suite, screenshots, contrast detector or network audit was run by this reviewer; root owns those verification results. No source implementation, .gitignore, commits or remote state were changed.

## Closure matrix — primary implementer verification

| Finding | Resolution and regression evidence |
|---|---|
| R1 | Persona scope map on login/logout; private contact and reading preference regression in app/store.test.ts |
| R2 | Reset removes only MoodPrint case/plan/support recovery prefixes; app/store.test.ts |
| R3 | SchoolView keyed by report ID; E2E edits 001 then opens 002 and verifies empty independent notes |
| R4 | Persisted analysis processing state distinguished from active local task; explicit retry; ai-flows.test.tsx |
| R5 | Duplicate merge compares confirmed text and preserves distinct corrections; ai.test.ts |
| R6 | Saved compose metadata, selected roleplay precedence, envelope-only metadata update and explicit template replacement confirmation; support.test.tsx |
| R7 | Scoped session recovery + useBlocker + beforeunload; stay/leave/reopen regressions; urgent route bypass |
| R8 | Plan draft baseline/revision and explicit reconcile before save; newer Home progress and independent local edits preserved; plans.test.tsx |
| R9 | Query-backed source-specific wizard identity, durable chat/evidence IDs and linkedCase update; incidents.test.tsx |
| R10 | ChatSession article ID/slug/source IDs persist across route change and reload; ai-flows.test.tsx |
| R11 | Knowledge URL params and aliases now applied; knowledge.test.tsx |
| R12 | Shared Field clones custom control ID/describedby/invalid attributes; field.test.tsx |

All original Important/Minor findings have an implementation fix and final regression coverage. Final root suite: 50 tests / 12 files; separate Playwright journeys and responsive evidence are in IMPLEMENTATION-REPORT.md. This is a root verification of the fixes, not a claim of an additional independent browser review.

Additional root visual checks fixed: mobile context selector density, hidden help link accessible name, article section contrast (axe recheck zero violations), caption minimum 12px, unopened dialog cleanup stealing focus (red→green regression), dangling case links after deletion (red→green regression). Two axe incomplete contrast cases remain explicitly documented for manual review; their declared text/background pairs were checked at 12.21:1 and 7.52:1.
