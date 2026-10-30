# Visual reference analysis

All six original PNGs were opened before implementation. Status: PASS (analysis). They are enlarged mobile concept crops; no device frame, status bar or illustrative data is application UI.

| Reference | Layout, inventory and rhythm | Behavior / data / missing states | Component mapping and existing gap |
| --- | --- | --- | --- |
| 01 `nhat_ky_cam_xuc` | Brand/date header, main title, five equal mood faces, emotion chips, factor chips; off-white, green selection, generous section gaps | Single mood, multi emotion/factor, account-local date, optional fields, keyboard radio group, selected state beyond color, empty/loading/errors | `JournalPage`, `JournalEditor`, mood choice/chip groups; replaces `/self` select-only form, retains shell. |
| 02 `ghi_lai_khoanh_khac` | Compact editor heading, text/audio/image/video tools, text area, playable audio, image tiles with remove, primary save | Combine media, draft/save/edit, recording pause/stop, permission denial, per-file retry/progress, native controls, deletion confirmation | `JournalEditor`, `JournalAttachments`, recording hook, private media APIs; current STT is not an attachment store. |
| 03 `kham_pha_them` | Four destinations in two-column grid, recent memories beneath; pale supporting colors, small illustrations | Real Nhịp route, prompt insertion, timeline, insights; no invented memories or counts; empty recent state | `JournalDiscovery`; below editor on mobile, contextual right column desktop. |
| 04 `lich_nhat_ky` | Month header with arrows, Monday-first seven columns, markers and legend, selected date entries, add action | Gregorian date arithmetic, account today, no future create, multiple entries/day, dates without data neutral, announced selected day/month | `JournalCalendar`, paged date-filtered entries; no current calendar. |
| 05 `khoanh_khac_cua_ban` | Chronological vertical rhythm, date/time and mood, excerpts, thumbnails and players, search/filter strip | Bounded pagination, text/mood/media filters, open/edit/delete, lazy media with preload none; empty/no results/error | `JournalTimeline`, `JournalEntryDetail`, signed lazy attachment component; current history is mood-only. |
| 06 `nhip_dong_hanh` | Existing Nhịp identity, supportive introduction, four query suggestions, writing prompts, bottom composer | Existing chat runtime, bounded saved-owner journal tool, validated original-entry citations, insufficient-data states, AI permission error | `JournalCompanion` entry surface links to existing assistant conversation; `MessageMarkdown` restricted journal links. |

## Typography, color and responsive decisions

Retain `styles/tokens.css`: ink `#243a35`, primary `#285c4b`, page `#f8f9f6`, selected `#e0e9de`; Segoe UI/system font supports Vietnamese. Body 16px and support 14px; use existing spacing scale and 14–16px radii. Reference low-contrast details become existing accessible muted text. Maintain 44px targets. Mood icons communicate the five feelings; use one consistent face family, and Lucide for actions.

At 360/390/430, use a single main column with compact five-choice row, wrapping chips, editor then discovery. At 768 and 1024, secondary material stays below or narrows safely. At 1440, keep the shell left, editor center and contextual discovery right. Persistent bottom navigation belongs to the shell; reserve its height plus safe-area inset in scroll content.

## Deliberate deviations

- Reference dates/day names and duplicated calendar numbers are illustrative and incorrect. Generate dates from account/server time; 28 October 2026 is Wednesday.
- No bold/italic/underline toolbar for plain-text storage; never display inactive formatting controls.
- Use real browser audio/video controls instead of decorative waveform playback.
- Keep historical daily notes separate and visibly labeled. No fake journal entries, streak pressure, invented mood scores or claims.
- Reuse existing companion artwork rather than tracing a new mascot from a screenshot.
