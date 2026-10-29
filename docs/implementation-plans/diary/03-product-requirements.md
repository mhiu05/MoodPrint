# Product requirements

Current implementation: **PASS for the scoped local product flows**. Evidence, hosted Storage verification and remaining live-provider/release gates are in [14](14-implementation-progress.md); the NOT_STARTED label below describes the planning checkpoint.

Status: NOT_STARTED at planning. Product decisions come from the supplied requirements; implementation choices are recorded here.

| ID | Priority | Requirement / acceptance |
| --- | --- | --- |
| J01 | P0 | Create multiple independent saved moments for the same account-local date without changing `Mood`; choose five moods, multiple emotions/factors, text optional for a quick check-in. |
| J02 | P0 | Persist draft server-side; text up to 10,000 characters; edit uses version, delete requires confirmation; error retains entered content and supports retry. |
| J03 | P0 | Mix image/audio/video attachments; record/pause/stop/replay audio, add/remove files, visible progress and errors; microphone failure offers file/text alternative. |
| J04 | P0 | Only owner reads/writes content and signs media. Private Storage objects, no public URL, no frontend server secret. |
| J05 | P1 | Mobile discovery below editor with working Nhịp, prompts, memories and insights destinations. |
| J06 | P1 | Monday-first monthly calendar with correct padding, neutral missing days, selected-day entries, previous/next and create for a valid day. |
| J07 | P1 | Timeline with bounded loading, owner text/mood/media filters, local timestamps, media previews and detail/edit/delete. |
| J08 | P0 | Existing Nhịp may read saved journal text by default under AI authorization, cite real source entries and respond to insufficient data; no other bot receives the tool. |
| J09 | P0 | Preserve legacy mood-note no-AI promise, current consent choices, export/erase/guest expiry/retention; no consent-toggle panel. |
| J10 | P1 | Keyboard/focus/labels/status/contrast and reduced motion; no horizontal overflow at six target widths, no bottom nav occlusion. |

## Scope choices

Journal retention initially follows the existing 90 account-local-day mood window to avoid silently expanding existing retention promises. Stored date/timezone are immutable creation semantics; edited entry time is distinct from occurrence date. Drafts are owner-readable but excluded from AI and default saved timeline/calendar. Draft listing/recovery must be explicit.

Initial limits: 10 attachments per entry; image 10 MiB, audio 20 MiB, video 50 MiB. Allowed MIME types are an explicit small list; SVG/HTML and unknown types rejected. Audio is a stored recording, not automatic STT. AI receives saved text and metadata, no image/audio/video bytes and no implicit media-provider processing.

No journal data enters matching, public profile or another person's chat. The new notice describes journal access at the editor before the first save and on the companion surface. Journaling works independently of AI/MEM/VOICE consent; opening Nhịp still requires the current AI authorization.
