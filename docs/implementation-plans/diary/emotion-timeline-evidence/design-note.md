# Journal timeline design note

Recorded 2026-10-30 for `/self/memories` on `test/local-2026-10-30`. This Read/Operate surface extends MoodPrint's incumbent visual system; it does not establish a new global visual world. The authorized work preserves other pages, navigation, editor, drafts, calendar, privacy and Nhịp. No research, personas or business goals have been invented.

## Overview

Saved moments form an open monthly timeline: month heading, quiet vertical rule, mood dot, date/time and written mood, prose, optional media and one contextual menu. The checked-in [composition reference](../../../diary/visual-references/05_khoanh_khac_cua_ban.png) informed this reading flow. Its filter chips and thumbnail deletion controls are absent in accordance with the current brief. A separately mentioned second screenshot was unavailable.

## Colors

The source of truth remains `frontend/src/styles/tokens.css`: background `--color-bg` (`#f8f9f6`), ink `--color-ink` (`#243a35`), supporting text `--color-muted` (`#52645d`), primary `--color-primary` (`#285c4b`) and rule `--color-divider` (`#d8ded5`). The timeline introduces no palette overrides. Dots use existing accent (`#b74f39`) for mood 1, warning (`#754c16`) for mood 2, muted for mood 3 and primary for moods 4–5. Visible emoji and mood labels accompany color.

## Typography

The existing display and body stack is `"Segoe UI", system-ui, -apple-system, Arial, sans-serif`. The timeline heading uses `clamp(1.5rem, 2.5vw, 2rem)`, line height `1.3` and letter spacing `-0.025em`. Month headings use `1.125rem` at weight `600`. Date/mood uses the incumbent label role (`0.9375rem`), changing to support (`0.875rem`) below 768px; detail links and progress use metadata (`0.8125rem`). Prose retains paragraphs with `white-space: pre-wrap`, a `68ch` maximum and line height `1.8` (`1.75` on phones). Long text has an explicit expand/collapse control.

## Layout

The page inherits `--reading-max: 45rem` (720px at the default root size), centered within the existing shell. Month groups are separated by `--space-8` (32px). Each month has a 1px divider rule, a 7px left offset and 32px content inset; the inset becomes 24px below 768px. Entries have no enclosing card border or fill and use 32px bottom spacing. The heading gap is 48px, reduced to 32px on phones.

Feed media is capped at 520px; a single image is capped at 360px with a reserved 3:2 cell. Multiple images reserve square cells with 8px gaps; the three-image feed uses three equal columns. Audio is capped at 440px. These layout and dot rules are scoped to the timeline/feed so compact journal entries keep their existing presentation.

## Elevation & Depth

The timeline itself adds no shadow: spacing, the thin rule and open prose establish hierarchy. The existing menu and lightbox retain their shared overlay treatments.

## Shapes

Mood dots are 14px circles with a 3px background border and 1px divider outline. The contextual trigger retains a 44px target, an 8px radius, the inherited selected fill on hover/open, and a primary 2px focus outline with 3px offset. The empty-state writing link has a 48px minimum height and uses the incumbent primary/hover colors.

## Components

`JournalTimeline.tsx` uses `JournalShared.tsx` feed entries and `JournalGallery.tsx` media rather than a parallel component system. Loading, empty, error/retry and incremental loading have explicit text; a load failure preserves already visible moments. Edit/delete remains in the contextual menu, with confirmation for deletion. Media uses authenticated access, retry on failed resources, native audio/video controls and a keyboard-accessible modal image viewer. Stored return-navigation metadata contains depth and scroll only, not journal content or signed media URLs.

## Do's and Don'ts

- **Do** retain the monthly reading order and existing moment-date semantics; updates must not reorder moments by edit time.
- **Do** preserve the existing shell, journal navigation, desktop rail and mobile bottom navigation.
- **Don't** propagate timeline layout or feed-specific dot/media styles to unrelated pages.
- **Don't** treat the neutral AI conversation world in root `DESIGN.md` as the journal palette.

## Evidence and preservation

Compared the Impeccable documenter reference, existing `PRODUCT.md`, root `DESIGN.md`, `.impeccable/design.json`, global tokens, `journal.css`, `JournalTimeline.tsx`, `JournalShared.tsx`, `JournalGallery.tsx`, `journalModel.ts` and `useJournalTimeline.ts` against the [implementation direction](../19-emotion-timeline.md), [evidence record](README.md), reference crop and all five actual captures: [390](timeline-390.png), [430](timeline-430.png), [768](timeline-768.png), [1280](timeline-1280.png), [1440](timeline-1440.png). The captures show the incumbent colors, system type, open monthly flow and retained navigation across phone, tablet and desktop sizes. Full-page phone captures place the fixed navigation at the first viewport boundary; they are not separate page sections.

`PRODUCT.md` and global `DESIGN.md` chiefly record the earlier AI-chat task; `DESIGN.md` explicitly limits its neutral overrides to `.bot-conversation.ai-conversation`. Reported pre-existing sidecar drift and an unset showcase build path were not repaired. This scoped note leaves those artifacts, `.gitignore`, source files, the plan and evidence README unchanged. Automated results, independent review conclusions and verification limits remain in the evidence record rather than being duplicated here.
