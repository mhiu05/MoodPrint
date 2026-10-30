# Emotion timeline implementation and verification

**Goal:** Replace the filter-heavy memories listing with an open, monthly emotion timeline.
**Spec:** User's attached “MoodPrint — Emotion Timeline Redesign” brief, 2026-10-30.
**Architecture:** Keep authenticated journal APIs, saved-only reads, existing ownership/retention and server ordering (moment localDate, createdAt, ID descending). Incrementally extend the visible prefix, refetching that prefix on load-more to reconcile offset changes caused by insertions/deletions. Never persist journal content or signed URLs.
**Stack:** Existing React 19, TypeScript, CSS tokens, Vitest, Playwright.

## Constraints and direction

- Current workspace and branch only; no branch operations, commits, merge or deployment. Preserve pre-existing `.gitignore` and `frontend/evidence/` changes.
- Scope: memories timeline, scoped feed styles, reused media hardening and relevant tests.
- Preserve sidebar, journal navigation, bottom navigation, editor, drafts, calendar, privacy and Nhịp.
- Read/Operate surface: inherited cream, green and neutral tokens, system type; centered 720px reading column, monthly headings, open entries, subtle mood dots, date/time, mood, prose and media. No filters, chips, numbered pagination or thumbnail deletion controls.
- The current workspace reference `docs/diary/visual-references/05_khoanh_khac_cua_ban.png` informs composition; a separate “second screenshot” was not attached to this turn.
- Reuse feed media and confirmed action menu rather than duplicate them. Keep global DESIGN.md scoped to the unrelated chat surface.

## Tasks

- [x] Add and run failing model tests for deterministic order, month grouping, duplicate replacement and cross-page merges.
- [x] Implement model helpers, progressive authenticated feed, monthly timeline and scoped responsive styling.
- [x] Harden existing gallery errors and modal focus without changing editor behavior.
- [x] Update old filter/paging E2E expectations and add empty/error/retry, append/reconcile, expand/menu/delete/edit-return and media tests.
- [x] Run typecheck, frontend suite, journal backend/integration checks where available, journal E2E and 390/430/768/1280/1440 render/axe checks.
- [x] Inspect screenshots, run Impeccable detector, fix material findings, obtain independent final review and record evidence/limitations.

## Review focus

- Backdated entries and identical timestamps remain ordered with the same comparator as the API.
- Load-more failures keep existing moments and permit retry; overlapping pages do not duplicate entries.
- Returning from an older entry restores loaded depth and scroll without caching sensitive content.
- Keyboard access to contextual actions, confirmation, text expansion and image lightbox.
- Long Vietnamese text, multi-image galleries, media errors, persistent mobile navigation and no horizontal overflow.

## Execution ledger

- Initial status: branch `test/local-2026-10-30`; pre-existing modified `.gitignore`, untracked `frontend/evidence/`.
- Ruling: follow the explicit autonomous implementation brief; no extra design approval or worktree creation.
- Ruling: preserve existing moment-date semantics; createdAt breaks ties within a moment day, updatedAt never affects chronology. No migration required.
- Model RED: 2 new tests failed because mergeTimelineEntries did not exist; GREEN: all 7 journal model tests passed after implementation.
- Browser RED: Tab left the single-image lightbox's close control; GREEN: explicit Tab wrap added and the full journal E2E suite passed.
- Final verification: TypeScript and production build pass; 118 frontend unit tests pass; 31 journal Playwright tests pass; all five timeline viewport axe scans return no violations.
- Backend journal checks: 37 passed, 31 skipped. PostgreSQL-marked tests require an explicitly configured disposable database. Docker daemon was unavailable, so real DB/full-stack verification is not claimed.
- Formatting: Prettier check and git diff --check pass. There is no frontend lint script or ESLint configuration; no separate JS/TS lint result is claimed.
- Impeccable source detector: no findings (`[]`); rendered accessibility checked separately with axe.
- Independent finish review: no P0/P1 or material visual findings at the inspected scope; one P2 exact-timestamp issue fixed after a RED→GREEN regression. Comparator preserves microseconds and normalizes offsets before ID tie-breaking.
- The review also identified pre-existing stale-photo display while awaiting the next signed URL. Added a delayed-access RED→GREEN E2E and keyed the lightbox media access by ID. Final independent verdict scored both fixes resolved, **ship at the fix-list scope**.
