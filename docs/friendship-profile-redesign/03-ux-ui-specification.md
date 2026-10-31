# Friendship Discovery — UX and UI specification

Status: planning only; proposed behavior for implementation. Read [01 evidence](01-current-state-audit.md), [02 requirements](02-product-requirements.md) and [04 contracts](04-technical-specification.md) together.

## 1. Approved direction and design authority

The approved composition is fixed: **Tìm một người bạn hợp gu 🌷**, three short questions, desktop builder on the left and an immediately updating public-card preview on the right. Recommendation cards contain a header, factual common-ground chips and a conversation starter. There is no alternative concept or dark reference-theme adoption.

Use `frontend/src/styles/tokens.css` and actual social/shell CSS. `DESIGN.md` describes a separate AI-chat scope; its palette does not apply here. This is an Operate surface: choices, understanding and consent take priority over decorative effects. Preserve navigation, private identity tab, existing relationships and safety controls.

## 2. Screen map and wireframes

Keep `/#/connect?tab=profile` and existing suggestions/requests/identity tabs. New eligible users with no published profile enter the builder directly after resources load; returning users see current publication status and `Chỉnh hồ sơ tìm bạn`. Draft restoration never opens publication confirmation automatically.

Desktop builder:

```text
Tìm một người bạn hợp gu 🌷
[Gợi ý] [Lời mời] [Hồ sơ tìm bạn] [Thông tin riêng]
[Existing-live / draft-restored status, when applicable]

Builder (flexible 60%)                 Preview (flexible 40%)
Bạn đang tìm kiếm điều gì?             Xem trước hồ sơ
( ) 💬 Có người tâm sự                 [seed] Bạn
( ) 🎯 Bạn chung sở thích              Đang khám phá bản thân
( ) 📚 Bạn cùng học                    Mình đang tìm
( ) 🌿 Bạn cùng trải nghiệm            [selected intention / placeholder]
                                      Những điều mình thích
Chọn những điều bạn thích     2/3      [actual featured interests]
[8 compact entry choices]              Cách mình kết nối
[selected tray] [Xem thêm sở thích]     [approach / placeholder]
[full-set preservation note if needed] [other public data disclosure]
                                      [privacy footer]
Bạn thích kết nối theo cách nào?
( ) 🌱 Từ từ làm quen
( ) ✨ Nói chuyện rôm rả
( ) 🎲 Cùng làm gì đó trước

[Xem lại trước khi hiển thị]
[Lưu bản nháp] [Đóng]
```

Mobile builder:

```text
Title + existing tabs
Câu 1/3                       [Xem hồ sơ]
Bạn đang tìm kiếm điều gì?
[4 full-width / wrapping choice cards]
[Tiếp tục]
[Lưu bản nháp] [Đóng]
(Existing MoodPrint bottom navigation)
```

Mobile Q2 contains the eight entries, selected tray and optional expansion. Q3 contains three choices. Back/Next is explicit; no automatic advance after selection. Q3 primary action is `Xem lại trước khi hiển thị`. Question index is presentation state only: switching device size never resets answers or causes a save.

Review is an editor stage, not a new account route. Left column becomes readiness/disclosure; right remains preview. On mobile the review is one scrollable page with card, public-data summary, consent text and final action. It is not a nested modal.

## 3. Layout, dimensions and breakpoints

All rem dimensions assume 16px root and must scale with user font settings. No fixed card height clips Vietnamese or enlarged text.

| Surface | Exact default |
| --- | --- |
| Discovery outer container | Scoped class on Discovery, max-width `var(--content-max)` = 70rem/1120px; width 100%; centered inside `.me-page`. Replace its 45rem reading constraint locally. Do not widen all reading pages. |
| Available-content ≥56rem (896px) | Two-column builder, `minmax(0, 3fr) minmax(20rem, 2fr)`; gap 24px (`--space-6`); form min-width 0. At 1120px this is about 658px/438px. |
| Available-content <56rem | Single column; compact preview trigger replaces inline preview. At tablet 768–1099px shell rail/gutters still reduce available width. Use a named discovery container query rather than viewport-only assumption. |
| Viewport ≥768px in single column | Show all three question sections in one document flow; preview dialog width min(34rem, available width). No artificial step pagination. |
| Viewport ≤767px | One question at a time, retained question navigation, full-width actions; dialog/review safe areas. Outer gutters inherited: 20px, 16px at ≤375px. |
| Question rhythm | Sections separated 24px; legend→hint 8px; hint→choices 12px; chip gaps 8px horizontal/vertical; form→actions 24px. Do not wrap every question in a raised card. |
| Q1 / Q3 choices | Q1 2 columns where the form content is ≥26rem, otherwise 1; Q3 one column to avoid squeezed text. Minimum height 48px, padding 12px 16px, gap 10px, radius 14px (`--radius-md`). Grow with text. |
| Compact chips | Min-height 44px, 12px horizontal padding, 8px icon/text gap, pill radius 999px; text 15px/1.4. No fixed width; wrap cleanly. |
| Public card | Width 100%, min-width 0, padding 24px desktop/20px mobile, radius 20px (`--radius-lg`), border 1px divider, optional existing raised shadow. Section gaps 20px, header gap 12px. |
| Avatar | 48×48px, decorative circular seed visual; no upload. |
| Recommendation grid | Available-content ≥48rem: 2 equal columns with 16px gap; below: 1. Each card at least ~360px at the two-column threshold; full-width in mobile. Top-aligned, auto height. |
| Noninteractive reason chips | Min-height 28px, padding 4px 10px, text 14px; not keyboard-focusable. Do not confuse them with selectable controls. |
| Dialog | Shared native Dialog, max-width 34rem, max-height `calc(100dvh - 32px)`; content scrolls; 20px padding mobile, 24px desktop. At 320px width keep ≥16px outer margin. Full-height mobile inset may shrink to 8px in short landscape. |

Sticky desktop preview: `position: sticky; top: 24px; align-self: start`. Disable stickiness when the card is taller than available viewport minus 48px (ResizeObserver or measured class) or the viewport height is below 700px. Never create a separately scrolling preview. Inspect ancestor overflow before relying on sticky positioning.

Mobile actions remain **in normal flow**, with primary first and full width. Do not add a second sticky bottom toolbar above MoodPrint's navigation. Existing `.me-page` already pads for `--bottom-nav` (72px), 24px and safe-area inset; retain this once, without double padding. Dialog uses the top layer and contains its own safe-area padding. Focused controls use scroll margin 16px; with sticky shell elements present, reserve their measured obstruction. No horizontal page overflow at 320px, landscape or zoom.

## 4. Typography, colors and component states

Use the existing Segoe UI/system stack; no font download. Screen title 32px/1.25 weight 650 desktop, 28px/1.3 mobile. Question legends 18px/1.4 weight 600; preview heading 18px/1.4; card alias 18px/1.4 weight 600; body 16px/1.6; hints 14px/1.5; counters 14px/1.4; metadata 13px/1.45. Starter label 12px/1.5 weight 650, letter-spacing .04em, exact uppercase copy. Use rem equivalents and allow wrapping.

| Role | Existing token / color |
| --- | --- |
| Page / card / soft inset | `--color-bg` #f8f9f6 / `--color-surface` #fff / `--color-surface-soft` #f0f3ed |
| Main / hint text | `--color-ink` #243a35 / `--color-muted` #52645d |
| Primary / hover / on-primary | `--color-primary` #285c4b / `--color-primary-hover` #214c3e / white |
| Default control border | `--color-border` #8c9a92; reserve #d8ded5 divider for noninteractive boundaries |
| Selected chip/card | `--color-selected-bg` #e0e9de, primary border/text and check glyph, weight 600 |
| Warning / error | `--color-warning` #754c16 on #fcedcd / `--color-danger` #9c352c on #fbeae7 |
| Disabled | `--color-disabled-bg` #e5e7e2 and `--color-disabled-text` #52645d; avoid whole-control opacity that reduces contrast |

States apply to every selector and action:

- Default: surface fill, 1px control border, ink label. Hover (hover-capable input only): soft fill and primary border. Selected takes precedence over hover.
- Selected: filled background plus check marker and programmatic checked/pressed state. Never rely on green alone. Native radio state remains the source of selection.
- Focus-visible: 3px primary outline, offset 3px; selected state remains visible; wrapper receives outline via input `:focus-visible`. Space reserved so outlines are not clipped. High-contrast mode uses system Highlight outline and text/check cues.
- Press: optional CSS `scale(.98)` for 100ms, no layout shift. No press transform in reduced motion.
- Disabled due to request: retain labels and dimensions, show disabled palette and reason/status. Read-only metadata chips do not use a disabled-looking selector style.
- Invalid: danger border plus inline explanatory text and `aria-describedby`; only show validation after Next/review attempt or relevant field interaction, not on first empty render.
- At featured maximum: unselected chips remain operable to announce the limit; do not silently disable them. Keep selected chips operable to remove. This intentionally differs from the old TagPicker max behavior.

Color contrast must be measured in future rendered states; the table reuses project colors but is not a substitute for verification. WCAG guidance and focus/contrast requirements are from the [W3C WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/).

## 5. Exact question choices and data meaning

### Q1 — Bạn đang tìm kiếm điều gì?

Native radio group, initially unanswered for new discovery metadata. A click immediately replaces intention and updates preview; other answers stay intact.

| Label | Proposed discovery ID | Canonical goal for a brand-new profile |
| --- | --- | --- |
| 💬 Có người tâm sự | `talk` | `friendship` |
| 🎯 Bạn chung sở thích | `shared-interests` | `shared-interests` |
| 📚 Bạn cùng học | `study` | `study-buddy` |
| 🌿 Bạn cùng trải nghiệm | `experiences` | `friendship` |

For existing saved/published profiles, Q1 is additive display intent and does not overwrite their existing goal. Under the group show the current canonical goal in the optional matching-settings disclosure. Helper: `Mong muốn này hiển thị trên thẻ. Gợi ý vẫn dựa trên sở thích và tùy chọn ghép bạn đã lưu.` This is a deliberate compatibility trade-off; changing the canonical goal remains an explicit advanced setting. Experiences does not auto-enroll anyone into an activity or promise in-person meetings.

### Q2 — Chọn những điều bạn thích

Hint: `Chọn tối đa 3 sở thích nổi bật trên thẻ của bạn.` Counter is `0/3` through `3/3`. The full set and featured subset have different purposes; all full-set interests remain public under the current API.

| Compact entry (fixed order) | Interaction / canonical ID |
| --- | --- |
| 🎧 Âm nhạc | Toggle `music`. |
| ☕ Cà phê | Toggle `coffee`. |
| 🎮 Chơi game | Toggle `games`. |
| 🎬 Xem phim | Toggle `movies`; backend taxonomy label may remain Phim ảnh. |
| 📚 Đọc sách | Toggle `reading`. |
| ✈️ Du lịch | Toggle `travel`. |
| 🎨 Sáng tạo | Button opens concrete picker: `photography`, `drawing`, `writing`, `crafts`, `singing`. Never commits a category ID. |
| 🏸 Thể thao | Button opens concrete picker: `walking`, `running`, `cycling`, `yoga`, `football`, `badminton`. Never commits a category ID. |

The two category launchers have `aria-haspopup="dialog"`, an accessible name such as `Chọn sở thích sáng tạo`, and a trailing chevron. They are not fake checkboxes. If any featured child is selected, the launcher shows a check and `· n` suffix but opens the chooser on activation; removal happens in the selected tray or chooser. More than one child may be featured, each counting as one of three. Music is excluded from the compact creativity launcher to avoid duplicate entry, while the full taxonomy's creative category remains unchanged.

Below choices, show the selected tray in selection order using actual labels, including selected IDs not represented by the initial eight. Each tray item has an accessible removal button (`Bỏ nổi bật: Vẽ`) with 44px target. Main chips and tray refer to the same IDs; they do not hold duplicate selections.

Fourth attempt: do not add, replace, shake or open a confirmation. Keep focus on attempted control, display and politely announce `Bạn đã chọn 3 sở thích nổi bật. Bỏ một sở thích để chọn thêm nhé.` Clear this notice after a successful removal/addition. The counter remains 3/3.

`Xem thêm sở thích` opens one shared interest dialog. Show the selected tray, a 44px search input, category select with the six taxonomy categories, at most eight results/page and `Trước`/`Sau` pagination. Default category is the first taxonomy category; search is local, case/diacritic-insensitive, across all 30 IDs. Empty search: `Chưa thấy sở thích này. Thử từ khác nhé.` Opening a compact group chooses its category subset. A count such as `6 kết quả` explains the current result set. Selections apply immediately to the editor; closing/Escape retains them. No duplicate Cancel semantics. `Xong` closes and restores focus to the launcher.

Legacy/full-set handling:

- If stored featured IDs exist, restore them. Otherwise propose the first three valid stored interest IDs in their existing order as the local featured view; no background write or republish. If <3 stored IDs, show all of them.
- Render `Bạn đã lưu N sở thích. Các sở thích còn lại vẫn được giữ để ghép bạn và có trong thông tin công khai.` and `Quản lý sở thích đã lưu` when the full set contains additional IDs. Always include a short `Sở thích đã lưu vẫn được giữ khi bạn bỏ nổi bật.` hint after the first save/restoration.
- De-featuring a previously saved ID keeps it in full matching data. De-featuring a newly added, never-saved ID removes that tentative addition. Document 04 defines reconciliation precisely.
- Full-set management is a separate mode of the same dialog, listing current stored IDs, with explicit `Xóa khỏi hồ sơ` actions. Inline note: `Xóa sẽ thay đổi thông tin công khai và gợi ý kết nối.` No confirmation per chip; deletion is draft-only until publication. Removing a featured ID removes it from featured too.
- Full max remains 10. If ten retained IDs prevent adding a new featured ID, leave state intact and show `Bạn đã lưu 10 sở thích. Xóa một mục trong “Quản lý sở thích đã lưu” để thêm sở thích mới.`
- Publish minimum remains **three full interests**, not three featured interests for legacy profiles. New profiles starting empty therefore need three selections; older full sets may feature one, two or three. Review gate explains `Cần ít nhất 3 sở thích đã lưu trước khi hiển thị hồ sơ.` Draft save is always allowed. Do not pretend one or two empty-new-profile picks are sufficient.

### Q3 — Bạn thích kết nối theo cách nào?

| Label | Proposed discovery ID | Meaning |
| --- | --- | --- |
| 🌱 Từ từ làm quen | `gradual` | Self-selected preferred pace; does not imply shyness or listening. |
| ✨ Nói chuyện rôm rả | `lively` | Self-selected conversational energy; does not imply directness. |
| 🎲 Cùng làm gì đó trước | `activity-first` | Interest in starting with an activity; does not opt into a specific activity. |

Native radio single selection. Keep legacy `style` unchanged; a new profile uses the documented neutral `balanced` matching default, disclosed in review and editable in matching settings. No mapping from these choices to listening/direct.

## 6. Live preview and complete public disclosure

Header: existing SeedAvatar visual, local name `Bạn`, neutral static status `Đang khám phá bản thân`. This is a local placeholder, never an invented member. Supporting note: `Khi kết nối, bạn dùng bí danh riêng cho từng người bạn.` Do not show session alias, private identity name or a real avatar without an independently authorized public-identity feature.

| Section | Empty | Answered |
| --- | --- | --- |
| Mình đang tìm | `Bạn muốn tìm một người bạn như thế nào?` | Exact selected intention label without adding inferred personality. |
| Những điều mình thích | `Sở thích của bạn sẽ hiện ở đây.` | Up to three actual featured IDs, in selection order, label lookup from taxonomy/UI map. |
| Cách mình kết nối | `Chọn cách làm quen bạn thấy thoải mái.` | Exact selected approach label. |

For a legacy profile with no discovery metadata, public display falls back to actual canonical goal/style labels; it never infers one of the new answers. In the editor unanswered new questions remain visibly unanswered. The owner must answer Q1/Q3 and feature at least one interest before adopting the new metadata at final review; an untouched old client can continue the legacy protocol.

Under primary sections, provide `Thông tin công khai khác` disclosure containing **the full interest set**, values, languages, canonical style/goal, activities, availability and strict-goal setting. Compact summary before the disclosure: `Ngoài các mục nổi bật, hồ sơ còn có N sở thích, giá trị và tùy chọn bạn đã lưu.` For an empty new profile use `Thông tin bổ sung sẽ được xem lại trước khi hiển thị.` On the final server review, expand this disclosure by default so publication cannot conceal the rest of the payload. Full-set interests are not private merely because they are unfeatured.

Footer: `Đây chỉ là bản xem trước. Hồ sơ không tự động công khai.` For an already-live profile add immediately above it: `Hồ sơ đang hiển thị vẫn giữ nguyên cho đến khi bạn xác nhận cập nhật.` For hidden/stale/needs_republish: `Hồ sơ đang tạm ẩn. Chỉ hiển thị lại khi bạn xác nhận.`

Keep the preview a read-only region, not `aria-live` on the entire card. One separate atomic polite status reports a short update (`Đã chọn Cà phê, 2 trên 3 sở thích nổi bật.`). Focus stays on the input; do not announce the whole card after every keystroke.

Mobile/tablet `Xem hồ sơ` opens shared Dialog with the same preview model, local-status label and `Tiếp tục chỉnh` action. Escape/close returns focus to trigger and retains selections. It never saves or fetches server preview. Only one modal may be open; close a picker before opening preview.

## 7. Review, save, publication and navigation

1. `Lưu bản nháp` is enabled for incomplete valid drafts. Disable controls during a save; on success show `Đã lưu bản nháp. Hồ sơ chưa được công khai.` With an existing live snapshot use `Đã lưu bản nháp. Hồ sơ đang hiển thị chưa thay đổi.` No automatic saving, localStorage or background beacon.
2. `Xem lại trước khi hiển thị` checks Q1, Q3, featured≥1 and full interests≥3. If invalid, focus a compact error summary with links to missing sections; on mobile navigate to the earliest invalid question. Do not disable the button without an explanation.
3. Enter review-preparation. Preserve existing values/languages. If missing, show one compact `Bổ sung để ghép bạn chính xác hơn` panel: `Chọn 2 điều bạn coi trọng ở một người bạn` (eight existing values, max 4), and `Ngôn ngữ trò chuyện` (vi/en, choose 1–2). No default values or guessed language. Both are public and the hint says so. Existing complete members skip this panel. This is a compatibility requirement, not a fourth/fifth main builder question.
4. Optional `Tùy chọn ghép bạn đã lưu` disclosure shows editable canonical goal/style, strictGoal, activities and availability, reusing taxonomy controls. Values/languages remain editable here when already complete. Preserve existing values on every question change. Before the first successful draft save, a genuinely new profile's canonical goal follows Q1 until explicitly overridden. After saving, or when editing any saved/published profile, changing Q1 changes only the displayed intention; canonical goal changes require the visible matching setting (04). A visible summary identifies the current goal and style even when settings are collapsed.
5. If readiness is already complete on entering review, save the captured draft then request server preview once. If the supplement was needed, user clicks `Xem bản được chia sẻ` to do the same. Changes in readiness settings invalidate any existing server preview; no automatic preview call per choice.
6. During request: `Đang chuẩn bị bản xem trước…`, fixed skeleton/card geometry, controls disabled, no final publish action. Success renders the exact returned public profile, full disclosure and `Bạn đồng ý tham gia gợi ý kết nối khi chọn Hiển thị hồ sơ. Bạn có thể ngừng hiển thị bất cứ lúc nào.` If consent is off explicitly say that this action turns matching participation on.
7. Final button is `Hiển thị hồ sơ`, or `Cập nhật hồ sơ hiển thị` for an existing live snapshot. Its dedicated click sends the current server preview token/version. No extra mandatory consent checkbox is needed: the visible review and explicit button preserve the existing consent mechanism. Failed/expired review never publishes.
8. `Chỉnh lại` returns to builder and invalidates review readiness/token. Final publication success announces `Đã hiển thị hồ sơ tìm bạn.` or `Đã cập nhật hồ sơ hiển thị.`, refreshes session/resources and opens suggestions. Do not publish on selection, dialog close, step completion, draft save or route exit.

Dirty exit via Close, tab, route link or Back: Dialog `Bạn muốn lưu thay đổi trước khi rời đi?`; actions `Tiếp tục chỉnh`, `Lưu bản nháp và rời đi`, `Bỏ thay đổi`. Safe continue action receives initial focus. Failed save keeps dialog/editor and intended destination pending. Clean exit is immediate. Browser close/reload uses native `beforeunload` only when dirty; browsers control its wording. Logout/session expiry clears private state and proceeds without attempting a save into an invalid session. Guarding route transitions must not defeat logout or the session reset.

## 8. Recommendation card

Use permitted `CandidateCardDTO`, pair alias/seed and published profile. Structure:

1. 48px seed avatar, wrapping alias, short selected intention; legacy fallback actual goal label. No neutral owner status claiming to describe a peer.
2. Up to three **server-provided** factual reasons as chips, preserving server order/wording. Existing qualitative match label may remain subtle; no percentage. Do not turn curated similarity into `Cùng thích` for different interests. New same-approach reason is future work unless server explanations explicitly support it; Q3 can appear as self-description in profile details.
3. Label `GỢI Ý BẮT ĐẦU CÂU CHUYỆN`, one 16px/1.6 starter in a soft inset with 12px padding, radius 8px. No copy button or randomize action is needed for MVP. It does not auto-send or add text to the invitation.
4. `Gửi lời mời kết nối` primary, `Bỏ qua` secondary, and visible text `Chặn`. Keep existing block confirmation. Below: `Thông tin công khai` disclosure using the same full-profile renderer. Do not remove public fields from preview while leaving them visible in API consumers.

Grounded starter priority is based on actual server explanation (04): exact shared music → coffee → movies → reading → games → travel; then a neutral opener. Example music copy: `Có bài hát nào bạn có thể nghe đi nghe lại cả ngày không?` If no proven supported subject exists, use `Gần đây có điều gì nho nhỏ làm bạn thấy vui không?` The generic prompt makes no claim about the other member. A music prompt must not be selected merely because the draft viewer likes music while the server candidate was based on an older published snapshot.

After successful invitation replace invite/skip with `Đã gửi lời mời kết nối` status; retain block. Busy states have explicit labels and keep card geometry. Skip/block success removes or refreshes affected cards and focuses the next card heading, or suggestions heading if none remain. A failed action keeps the same card with an inline retryable error. An expired reference offers reload; do not silently repeat the action with a different candidate reference.

Do not add a candidate-only report action: today's server requires prior interaction. Preserve report access in human chat including after block/end. Candidate reporting requires a separate policy/API project.

## 9. Loading, empty and error inventory

| Situation | UI / recovery |
| --- | --- |
| Initial taxonomy/draft/publication loading | `Đang tải hồ sơ…`; one builder/preview skeleton, `aria-busy` on loading region, no pretend selected answers. |
| One initial resource failed | ErrorNotice + `Thử lại`; keep valid resources cached; no editable fake fallback taxonomy or draft version 0 overwrite. |
| No candidates, eligible live profile | `Chưa có gợi ý phù hợp lúc này.` + `Bạn có thể quay lại sau hoặc cập nhật những điều muốn chia sẻ.` Actions `Tải lại gợi ý`, `Chỉnh hồ sơ`; no invented people or pressure to change interests. |
| No live profile | `Hiển thị hồ sơ để nhận gợi ý kết nối.` + `Mở hồ sơ tìm bạn`. |
| Candidate refresh pending | Retain prior cards as busy/stale and disable their mutation actions until refreshed; one loading status. Initial load shows two static card skeletons. |
| Save network failure | `Chưa lưu được bản nháp. Lựa chọn của bạn vẫn còn ở đây.` + retry; dirty remains true. |
| 409 STALE_VERSION | `Bản nháp đã được cập nhật ở nơi khác.` Keep local choices, offer `Xem bản mới nhất` or `Tiếp tục chỉnh bản này`; explicit second overwrite confirmation after fetching latest version, never automatic last-write-wins. |
| 409 PREVIEW_CHANGED / 15-minute expiry | `Bản xem trước đã thay đổi hoặc hết hạn. Xem lại trước khi hiển thị nhé.` Clear publish readiness; `Tạo lại bản xem trước`; no automatic publish retry. |
| Full/featured limits | Exact inline messages in Q2; polite status, unchanged selection. |
| 403 age/restriction/consent change | Replace actions with server-authoritative StatePanel; refresh session. Do not expose details of peer restriction/deletion. |
| 401 / account switch | Clear editor, preview, candidates and pending callbacks; use existing sign-in/session recovery. No cross-account restore. |
| 429 quota | Honor retryAfter when present, keep context and server message. Do not fabricate a countdown if no deadline is supplied. |

## 10. Motion and accessibility contract

Simple transitions use existing CSS duration/easing tokens. No new GSAP dependency, ScrollTrigger, character animation, question slide or confetti. Existing Dialog's GSAP 220ms entrance remains the one justified shared timeline, with matchMedia cleanup already implemented. [GSAP matchMedia documentation](https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/) supports breakpoint/reduced-motion scoping and reversion.

| Interaction | Duration / easing | Reduced motion |
| --- | --- | --- |
| Chip fill/border, radio selected state | 100ms `--ease-state`; state visible immediately | No transform/transition. |
| Preview changed section | Optional opacity .85→1, 160ms `--ease-state`; no remount/focus loss, no height tween | Immediate text replacement. |
| Mobile question navigation | Immediate swap, focus new legend; no CSS translate carousel | Same. |
| Recommendation card arrival | Optional opacity 160ms `--ease-enter`, all cards together, no stagger | Immediate. |
| Skeleton | Static soft blocks; no shimmer | Static. |
| Save success | Persistent inline status; optional opacity 160ms; no automatic focus move | Immediate. |

Semantics: fieldset/legend for questions; native radios and visually hidden (not display:none) checkboxes for direct interest pills. The glyph is hidden, not the semantics. Each interest label includes emoji as decorative `aria-hidden`; accessible name is text. Category launchers use buttons. Native radio arrow navigation and Space checkbox toggling must work; no custom roving code is needed for these inputs. Keep existing roving discovery tabs.

Dialogs have accessible titles, close actions, focus trap, Escape and trigger-focus restoration. Form error summary receives programmatic focus and links to fields; messages are associated to controls. Do not announce the counter and the identical selection status twice; use one combined polite region per action. New question focus uses a legend/heading with tabIndex -1, never an arbitrary body jump. All controls/actions have ≥44×44px hit areas; explanatory text is never only a tooltip. Test screen readers, forced colors, keyboard-only, touch, reduced motion and browser zoom as described in 06.

## 11. Design references and licensing review

- [Impeccable repository](https://github.com/pbakaus/impeccable) and [Operate guidance](https://raw.githubusercontent.com/pbakaus/impeccable/main/.agents/skills/impeccable/reference/operate.md), reviewed 2026-10-31: apply consistent familiar controls, restrained hierarchy, meaningful states and motion. This specification's application is an inference for MoodPrint, not copied UI source. The upstream [Apache-2.0 license](https://raw.githubusercontent.com/pbakaus/impeccable/main/LICENSE) requires preserving applicable notices if code is later copied; no implementation was copied here.
- [GSAP repository](https://github.com/greensock/gsap): already present in the project. The current [standard license](https://gsap.com/community/standard-license/) permits ordinary website/app use subject to its terms and restricts competing visual-animation tools. MoodPrint's use appears to fit ordinary product UI (design assessment, not legal certification). Preserve notices and recheck the locked package license before redistribution; no new plugin/library is required.
- [W3C WCAG 2.2 reference](https://www.w3.org/WAI/WCAG22/quickref/): validation target, not a claim of compliance. Exact accessibility behavior above must be tested, not inferred from a screenshot.
