# Personal timeline redesign

Status: **PASS** for the journal surfaces exercised by Playwright.

## What changed

| Area | Change | Files |
| --- | --- | --- |
| Destinations | Nhật ký nav is Hôm nay, Khoảnh khắc của bạn, Nhìn lại, and Lịch nhật ký. | `JournalShared.tsx` |
| Feed | Saved entries group by account-local day (Hôm nay, Hôm qua, or a date) and by month. Newest-first order stays the API order. Paging remains 12 items. | `JournalTimeline.tsx`, `journalModel.ts` |
| Cards | Time, mood, text with Xem thêm after 220 characters, emotion/factor tags, edit, and confirmed delete. | `JournalShared.tsx` |
| Images | One, two, three, and four-up grids. Further images show +N. A dialog lightbox supports next, previous, and Escape. URLs load when the cell is near the viewport. | `JournalGallery.tsx`, `journal.css` |
| Audio and video | Native controls, `preload="none"`, no timeline autoplay. Signed URLs load when the player is near the viewport. | `JournalGallery.tsx` |
| Text-only moments | No empty media slot. | `JournalEntryCard` |
| Return scroll | Opening or editing a card stores `journal-feed-scroll` and the feed restores it once. | `JournalShared.tsx`, `JournalTimeline.tsx` |
| Composer | Mood selection uses a short GSAP scale when motion is allowed. Retention and text-only Nhịp copy sit under the form. | `JournalEditor.tsx` |
| Prompts | Four optional Vietnamese questions, including smile, thought, thanks, and what made the day memorable. | `journalModel.ts` |
| Nhìn lại | Companion page keeps Nhịp questions and links to the existing daily mood chart. | `JournalPage.tsx` |
| Motion | `useMotionPolicy` gates GSAP. Reduced motion skips the feed and mood animations. Contexts use `useGSAP` with revert. | `JournalEditor.tsx`, `JournalTimeline.tsx` |

Calendar behavior was kept: month navigation, mood marker, multi-entry count, and day list. It does not invent moods for empty days. Expired entries stay outside the 90-day query window already enforced by the API and `activeMonthBounds`.

## Tests

- `journalModel.test.ts` covers day labels and grouping. Frontend unit suite: 103 passed.
- `tests/e2e/journal.spec.ts` passed, including filters, paging, six widths, axe, and the timeline image becoming visible without a separate “Xem tệp đính kèm” step.
- The timeline evidence PNG uses the suite’s 1×1 fixture image, so it does not demonstrate a photographic collage. The layout CSS is what a real image fills.

## Critique

The rendered mobile check-in and desktop composer keep the warm off-white page, sage selection, and existing left navigation. The timeline reads as a dated list rather than a table. Important points that remain:

- Card actions sit in one row. Delete is confirmed, but it is still close to Edit on a narrow phone.
- The retention sentence is plain and below the feed. It is accurate, including the provider-backup limit.
- Gallery motion is a short entrance only. There is no scroll-jacking.

No Critical contrast or axe failure was reported on the journal page, calendar, timeline, or companion scan in `journal.spec.ts`.
