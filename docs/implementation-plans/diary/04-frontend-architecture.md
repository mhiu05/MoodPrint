# Frontend architecture

Current implementation: **PASS**. Actual consolidated component paths are mapped in [09](09-design-system-and-gsap.md); [14](14-implementation-progress.md) records browser/fullstack results. The architecture below is the committed planning baseline.

Status: NOT_STARTED. Extend React Router within `features/real/RealApp.tsx`; retain `useSession`, `ErrorNotice`, `Button`, `Dialog`, tour draft blocker and shell navigation.

| Target | Responsibility |
| --- | --- |
| `features/real/journal/JournalPage.tsx` | `/self` editor + discovery; section navigation and owner-only loading state. |
| `journal/JournalEditor.tsx` | Mood/emotions/factors/date/text, immutable server entry identity, draft/save/version/conflict handling, dirty guard. |
| `journal/JournalAttachments.tsx` | File selection/recording, preview/remove, serialized upload/retry and lazy signed playback. |
| `journal/JournalCalendar.tsx` | Month grid and selected-day entry list via date-range API. |
| `journal/JournalTimeline.tsx` | Query/filter/pagination and entry excerpts; no eager historical media transfer. |
| `journal/JournalEntryDetail.tsx` | Authenticated `/self/entry/:id` read/edit/delete, 404/unavailable state. |
| `journal/journal.css` | Scoped responsive layout using incumbent tokens. |
| `api/journal.ts` | Shared typed journal API and upload helper; generated contracts remain API authority. |
| `features/real/MessageMarkdown.tsx` | Allow only validated local UUID journal links; external model links remain inert. |

Route naming may consolidate files where responsibility remains clear; final progress records actual paths. Keep existing daily mood UI at `/self/daily` and provide a named historical-data link. Existing `MoodInsights` may remain for daily mood only and must not imply journal aggregation.

## State and errors

Use server drafts, not automatic sensitive localStorage. Track unsaved editor state separately from animation. Save text metadata before uploading, retaining the same entry/media reservation on retry. Disable duplicate actions while in flight. Keep failed pending attachments visible and allow removal/retry. A stale write shows a conflict and preserves user text, never silently overwrites with a newly fetched version.

Use beforeunload and route transition protection for dirty text/recording; request confirmation before discarding in-app. Object URLs and microphone tracks must be released at remove/unmount. Loading, empty, offline/failed save, permission-denied and unavailable media are visible states. Do not persist signed access URLs in journal payloads or browser storage.
