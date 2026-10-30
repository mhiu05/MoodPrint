# Emotion Timeline evidence — 2026-10-30

The screenshots show the actual Vite/React interface at `/self/memories`, rendered in Chromium by `frontend/tests/e2e/journal.spec.ts`. Content and attachments belong to synthetic authenticated test accounts, with API interception restricted to tests. No sample entries were added to the production app or user databases.

| Width | Capture |
| --- | --- |
| 390 | [Phone](timeline-390.png) |
| 430 | [Large phone](timeline-430.png) |
| 768 | [Tablet](timeline-768.png) |
| 1280 | [Desktop](timeline-1280.png) |
| 1440 | [Wide desktop](timeline-1440.png) |

Full-page captures include the existing fixed mobile navigation at the bottom of the first viewport. Content remains scrollable behind it; existing page bottom spacing permits reaching the final entry. Desktop retains the existing left rail. Reduced motion was enabled for these captures.

## Automated evidence

- `npm.cmd run typecheck`: pass.
- `npm.cmd run build`: pass.
- `npm.cmd test`: 118 passed (23 files).
- `npm.cmd exec playwright -- test tests/e2e/journal.spec.ts`: 31 passed (1.4 minutes).
- All target timeline viewports: no horizontal overflow and no axe violations for WCAG A/AA rules run by the suite.
- Backend `.venv/Scripts/python.exe -m pytest tests/test_journal.py tests/test_journal_contract.py tests/test_journal_ai.py tests/test_journal_storage.py tests/test_journal_migration.py -q`: 37 passed, 31 skipped (disposable PostgreSQL unavailable).
- Prettier check and `git diff --check`: pass. No standalone frontend lint command is configured.
- Impeccable source detector on timeline, shared entries, gallery and journal CSS: zero findings. Browser rendering was audited with axe; a rendered Impeccable detector scan is not claimed.

Coverage includes calendar navigation, server drafts, uploads/retries, recording, saved-only empty state, 66-entry loading across the API's 50-item cap, an insertion between loads, retry without losing visible entries, deterministic ties, monthly headings, text expansion, keyboard menus and delete confirmation, older-entry editing with return depth/scroll, expired/broken attachment recovery, lightbox focus and Escape, and real native audio/video playback with generated fixtures.

## Design review

Applied the installed [Impeccable](https://github.com/pbakaus/impeccable) critique, distill, adapt, audit and polish principles.

- P1 removed: filter form and page replacement interrupted memory browsing; replaced with saved-only monthly reading flow and incremental loading.
- P1 fixed during verification: lightbox Tab focus could leave the close button; native modal isolation plus explicit wrap now pass keyboard testing.
- P2 fixed: a failed image/video/audio resource could remain a broken player; shared media access now presents a retry action on element errors.
- P2 fixed: image-loading layout shifts; reserved thumbnail aspect ratios stabilize the reading position.
- P2 fixed: action density and repeated metadata; the feed uses one date/mood header, a discreet contextual menu and preserved paragraphs.
- P2 fixed after independent review: preserve the backend's microsecond timestamp precision before using ID ties; regression also covers equal instants with different timezone offsets.
- P2 fixed after independent review: switching gallery images now clears the previous URL while awaiting the next one. A delayed-response regression failed before the change and passed afterward.
- Independent review found no P0/P1 or material visual issues in its inspected scope. Its final verdict pass scored both listed fixes **resolved**, disposition **ship at the reviewed fix-list scope**. The final automated verification gate subsequently passed.

## Files changed

- `frontend/src/features/real/journal/JournalTimeline.tsx`: monthly timeline, empty/loading/footer states and return scroll.
- `frontend/src/features/real/journal/useJournalTimeline.ts` (new): authenticated prefix loading, reconciliation, abort/retry and navigation depth.
- `frontend/src/features/real/journal/JournalShared.tsx`: feed date/mood header, contextual menu, text expansion semantics and navigation metadata.
- `frontend/src/features/real/journal/JournalGallery.tsx`: media error recovery, native modal focus, keyed image navigation.
- `frontend/src/features/real/journal/journalModel.ts` and `journalModel.test.ts`: exact chronology, deduplication and month grouping.
- `frontend/src/features/real/journal/journal.css`: scoped open-feed composition, mood markers, media sizing and responsive rules; removed filter/pagination styles.
- `frontend/tests/e2e/journal.spec.ts`: updated browsing tests, regression/interaction/playback cases and five-width screenshots/axe.
- `frontend/tests/fullstack/journal.spec.ts`: removed obsolete search steps while retaining its real owner isolation/edit/delete flow. Updated but not run because the disposable DB is unavailable.
- `frontend/tests/fixtures/journal/`: three test-only photographs and source provenance.
- `docs/implementation-plans/diary/19-emotion-timeline.md` and this evidence directory: implementation record, captures, detector result and design note.

Current branch: `test/local-2026-10-30`. Changes are uncommitted. No branch creation/switch/reset/pull/rebase, merge or deployment was performed. The pre-existing modified `.gitignore` and untracked `frontend/evidence/` were preserved.

## Verification limits

No authenticated live account, real signed-media service, PostgreSQL/full-stack run, physical phone, Safari or Firefox verification was performed. The separately mentioned “second screenshot” was not attached; comparison used the checked-in approved timeline crop. The implementation preserves the existing moment-date semantics rather than introducing a new timestamp field or migration. Offset reads have no transaction-wide snapshot across requests; the visible prefix is reconciled on each load to handle changes between clicks.

Global `DESIGN.md` describes the unrelated AI chat surface and was preserved. Impeccable reported pre-existing design-sidecar drift and an unset showcase build path; neither affects this code-first app surface and neither was repaired as a side effect.
