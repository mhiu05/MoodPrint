# Design system and GSAP

Status: PASS for the implemented journal design-system and motion scope. The final visual reviewer returned `ship` after inspecting all 14 final PNGs, with no P0/P1 visual findings. See [evidence](evidence/) and the [verification ledger](14-implementation-progress.md) for the final review and application checks.

The journal extends the incumbent Operate surface: `frontend/src/styles/tokens.css`, `frontend/src/components/UI.tsx`, the existing shell, companion artwork and `components/motion` conventions remain the authority. The Impeccable context launcher ran once successfully. This work introduces no new visual identity or global design system; root `PRODUCT.md`/`DESIGN.md` and agent/skill configuration remain outside this documentation change.

## Direction contract

Bright warm page, calm sage selected states, dark green primary actions, clear Vietnamese body text. The implemented task progresses mood → details → influences → moment → save; discovery follows below on narrow screens and sits beside the editor on wider screens. Section gaps exceed internal label gaps. Restrained white surfaces, dividers and small companion assets preserve the hierarchy established in [02](02-visual-reference-analysis.md).

| Element | Existing token / rule |
| --- | --- |
| Page / surface | Existing `--color-bg` (`#f8f9f6`), `--color-surface`, `--color-surface-soft`; journal dividers alias `--color-divider`. |
| Primary / selected | Existing `--color-primary` (`#285c4b`), `--color-selected-bg` (`#e0e9de`); mood radios and chip checkboxes also expose checked state, borders and check marks. |
| Text / help / errors | Existing `--color-ink` (`#243a35`), `--color-muted`, `--color-danger`; inherited shared error and button treatments. |
| Type | Existing `--font-body` (Segoe UI/system), 16px body, `--text-support` (14px), `--text-meta` (13px); mobile mood labels use 13px. |
| Spacing / corners | Existing spacing rhythm and `--radius-md` (14px) on major surfaces; local 12px mood/media corners and pill chips support their specific controls. |
| Targets / focus | Existing 44px target minimum, visible native or shared focus treatment, explicit focus outlines around visually styled radio, checkbox and file inputs. |

Source comparison confirms that journal surfaces consume the existing semantic tokens rather than redefining them. The five face fills and two discovery icon accents are local illustration colors in `journal.css`; they do not replace text, action or selected-state tokens.

## Implemented components

All journal files below are under `frontend/src/features/real/journal/`.

| Component | Actual source and role |
| --- | --- |
| Journal page / discovery / companion | `JournalPage.tsx`: `JournalPage`, inline discovery links and recent entries, plus `JournalCompanion`; discovery is a page section, not a separate `JournalDiscovery.tsx`. Reuses `BotAvatar` from `frontend/src/companions/Avatar.tsx`. |
| Editor / choices / save feedback | `JournalEditor.tsx`: native date input, five-radio mood group, emotion/factor checkboxes, plain-text writing, shared buttons, draft/saved/conflict states and live save receipt. |
| Attachments | `JournalAttachments.tsx`: image/audio/video file controls, recording, local previews, progress/retry/removal and saved media. Local audio/video previews use native `controls` with `preload="metadata"`. |
| Shared journal UI | `JournalShared.tsx`: `MoodFace`, `JournalNav`, `JournalBack`, `JournalEntryCard` and `JournalMediaPreview`. Saved audio/video use native `controls` with `preload="none"`; entry-card previews open on demand. |
| Calendar / timeline / detail | `JournalCalendar.tsx`, `JournalTimeline.tsx`, `JournalEntryDetail.tsx`; shared navigation, faces, entries and media keep these routes consistent. |
| Styling / motion policy | `journal.css`; existing `frontend/src/styles/tokens.css`, `frontend/src/styles/me2we.css`, `frontend/src/components/UI.tsx` and `frontend/src/components/motion/useMotionPolicy.ts`. |

`MoodFace` is one inline SVG family with five expressions, reused in the editor, calendar, legend and entry summaries. Lucide supplies action and navigation icons. Existing Mây/Nhịp artwork supplies companion identity. Native media controls replace the reference's decorative waveform; the plain-text editor has no inactive formatting toolbar.

## Responsive behavior

| Width / breakpoint | Implemented behavior |
| --- | --- |
| 1200px and above | Editor plus 300px discovery column; gap uses `clamp(32px, 4vw, 64px)`. The existing left shell remains in place. |
| 1024–1199px | Discovery narrows to 260px with a 28px gap; mood controls reduce internal space and face size. |
| 1023px and below | Editor becomes a single main column; discovery moves after it with a divider and two-column destination links. |
| 767px and below | Existing shell changes to bottom navigation; journal navigation wraps, intro artwork reduces to 68px, mood faces to 35px, chips wrap and the primary save action spans the row. Timeline filters use two columns, with mood spanning both. Calendar stays seven columns. |
| 375px and below | Calendar horizontal padding becomes 6px and column gaps 1px to preserve date targets. |

The inherited token/shell breakpoints also remain at 1099px, 767px and 375px for gutter/rail behavior. Mobile scroll content reserves `--bottom-nav` (72px), 24px clearance and `env(safe-area-inset-bottom)` in `me2we.css`. The separate viewport capture `mobile-save-clearance.png` shows both save actions above the fixed navigation; a full-page capture may place the fixed bar across an earlier scroll position.

## Motion

The installed GSAP 3 and `@gsap/react` are reused only for the save receipt in `JournalEditor.tsx`: after a successful draft or moment save, the receipt moves from `y: 4` to `y: 0` over 0.22s with `power2.out`, then clears its transform. `useMotionPolicy().animate` gates the tween on both reduced-motion preference and document visibility. `useGSAP` scopes it to `receiptRef`, declares `[receipt, animate]` dependencies and uses `revertOnUpdate: true` for update/unmount cleanup.

The live status text is rendered immediately; save success and form state do not await animation. No layout-critical content starts hidden. Mood/chip hover and selection use the incumbent CSS duration/easing tokens, with journal transitions/animations removed by `prefers-reduced-motion: reduce`. The implemented scope has no GSAP panel/attachment entrance, typing animation, ScrollTrigger or scroll hijacking.

## Final rendered evidence

All 14 PNGs in [evidence](evidence/) were opened for the documentation pass and final visual review:

- Experience captures: [desktop check-in](evidence/01-checkin-desktop.png), [mobile check-in](evidence/01-checkin-mobile.png), [media editor](evidence/02-editor-mobile.png), [discovery](evidence/03-discovery-mobile.png), [calendar](evidence/04-calendar-mobile.png), [timeline](evidence/05-timeline-mobile.png), [companion](evidence/06-companion-mobile.png).
- Responsive captures: [360](evidence/viewport-360.png), [390](evidence/viewport-390.png), [430](evidence/viewport-430.png), [768](evidence/viewport-768.png), [1024](evidence/viewport-1024.png), [1440](evidence/viewport-1440.png).
- Fixed-navigation clearance: [mobile save viewport](evidence/mobile-save-clearance.png).

The evidence shows the selected five-face group, readable Vietnamese labels, active journal navigation, wrapped choices, native media editor, two same-day calendar/timeline entries and the responsive editor/discovery hierarchy. Captures use synthetic browser fixtures; the image fixture is intentionally a one-pixel placeholder. They establish the rendered UI scope. Hosted provider checks and exact test commands/results belong to [14](14-implementation-progress.md).
