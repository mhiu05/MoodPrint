# MoodPrint UX redesign — implementation progress

Implementer: Claude Code. Branch: `feat/ux-redesign` (from `main` @ `5872b72`). Not pushed, merged or deployed.
Status vocabulary: **PASS** (observed command/browser output), **PARTIAL**, **FAIL**, **BLOCKED**, **NOT RUN**.

## T00 — Branch and baseline

| Item | Result |
|---|---|
| Starting `git status --short` | ` M .gitignore` (adds `docs/ux-redesign/evidence/`), `?? docs/` (planning package). No toolkit intent-to-add entries present. Both left untouched and unstaged. |
| Source drift vs `evidence/audit-start.json` | HEAD identical (`5872b72`); 162/162 recorded application/dependency SHA-256 hashes match. No drift to reconcile. |
| Node / toolchain | Node v24.13.0 (CI/Docker use Node 22 — R04 still open). |
| `npm.cmd run typecheck` | exit 0 |
| `npm.cmd test` | exit 0 — 10 files, 54/54 tests |
| `npm.cmd run build` | exit 0 — `index` 495.31 kB (gzip 160.73 kB), `MessageMarkdown` 119.99 kB (gzip 37.08 kB), CSS 38.62 kB (gzip 8.59 kB) |
| `npx playwright test` (default config, Vite on 127.0.0.1:5173 started by Playwright; port was free) | exit 0 — 68/68 passed (1.3 min) |
| Baseline production build kept for paired performance runs | yes (local workspace copy, not committed) |

Planning documents under `docs/ux-redesign/` (00–18, 99) and `evidence/` stay uncommitted user work; only this progress file is added to Git by the branch.

## Phase 1 — P1 journeys (T01–T03)

| Task / finding | Change | Regression evidence (actual runs) | Status |
|---|---|---|---|
| T01 / F01 | Starter chips insert into the draft at the caret (separator, 500-char guard, focus, status "Đã thêm gợi ý vào ô nhắn."); no consent/conversation/message write until explicit Gửi/Enter. | `real.spec.ts`: 4 new tests RED (chip POSTed) → GREEN; real+chat-history 37/37 | PASS |
| T02 / F02 | `useActivity` adds `catalogStatus`, `catalogError`, `reloadCatalog`, kind-scoped `inviteError`. Failed catalog keeps the entry and shows alert + Thử lại; empty catalog (backend activities-off) still hides entry. Failed invite shows alert beside that activity, keeps plan/cycles; retry reuses the same Idempotency-Key. "Mời cùng chơi" → "Mời tham gia". | `activities.spec.ts` 2 new tests RED → GREEN; 429 per-kind test kept; activities 12/12, states 5/5 | PASS |
| T03 / F03 | Memory (AI off / MEM off) and Messages (MATCH off) now explain the real opt-in: Send in a conversation, approve a new proposal, review + "Hiển thị hồ sơ" (`/connect?tab=profile`). Verified against backend: MEM granted in `ai/memory.py` confirm, MATCH in `social/routes.py` publish. | `ux-redesign.spec.ts` 3 tests RED → GREEN | PASS |
| T03 / F04 | Chat block dialog: "Việc chặn không thể hoàn tác trong ứng dụng.", loss of access, report stays available; cancel focused first (`data-cancel` was missing). Discovery block copy already truthful. | `ux-redesign.spec.ts` RED → GREEN | PASS |
| T03 / F11 | Client fallback for message-less failures: "Chưa hoàn tất yêu cầu. Bạn hãy thử lại."; network: "Chưa thể kết nối. Bạn hãy thử lại." (no blanket "input kept" claim). Server validation messages pass through. | `client.test.ts` 3 new unit tests; `ux-redesign.spec.ts` non-JSON 500 test | PASS |
| T03 / F13 | Backend `EXPORT_TOO_LARGE` copy (AI conversation + account export) no longer promises page export / support request. No new API (R06 remains a product decision). | `backend/tests/test_privacy_lifecycle.py` assertion RED on old copy → GREEN; file 9/9 against disposable `moodprint_uxr_test` | PASS (copy) / R06 open |
| T03 extras | Moderation resolution enums mapped to Vietnamese; first-send consent sentence from `05`; read-only chat no longer links to Settings when the AI service is down. | `ux-redesign.spec.ts` 3 tests | PASS |

Full run after phase: `vitest` 57/57, `playwright` 82/82, `ruff check app tests` clean.

## Phases 2–5 — foundations, navigation, motion, AI chat and memory (T04–T09)

| Task | Change | Evidence (actual runs) | Status |
|---|---|---|---|
| T04 / F08 | Single token authority (`tokens.css`): type roles (16/15/14/13/12–13px), surface-soft/selected-bg, 44px targets, 48px controls, gutters, motion tokens, `color-scheme: light`. `me2we.css` rewritten around 0–767 / 768–1099 / ≥1100 / ≥1440; 104px rail + 248px pane desktop, 72px rail and one surface on tablet; App.module trailing overrides removed (dialog text was 13px). Persona descriptions wrap. | 3 V-TOKENS/V-REFLOW browser tests RED (15px body, 10px nav/starters) → GREEN at 320/375/390/768/1280/1440; screenshots reviewed (`evidence/redesign/*-t04.png`) | PASS (emulated widths) |
| T05 / F10, F14 | Five destinations Trợ lý · Cảm xúc · Tìm bạn · Tin nhắn · Cá nhân on existing routes; `useRouteFocus` focuses the visible destination heading (conversation heading preferred, hidden roster skipped), never after the person moved focus; thread switch focuses its heading. Roster copy + specific no-result state. | 4 tests; mobile focus was `BODY`, desktop was roster h1 → GREEN | PASS |
| T06 | `useMotionPolicy`/`resolveMotionPolicy` (reduced before mount + live, visibility). Route-wide GSAP fade removed; dialog entrance 8px/220ms, clears only `transform`; no `clearProps:"all"`. | vitest 3; `motion.spec.ts` route opacity + dialog travel RED → GREEN, reduced + rapid open/close guards | PASS |
| T07 / F06 | `deriveAIActivity` + `AIActivityStatus` (one polite live region, 20px slot, Dừng). Labels only from real phases. Stop waits for terminal event; completed-wins shows reply; late cancel errors ignored. `thinking-orbs@0.3.2` gate: npm metadata gitHead `5e7afad`, MIT, peer `react>=18`, no deps, no install scripts, `theme/paused/size` API; canvas forced `role=presentation aria-hidden`. Lazy chunk 26.41 kB (gzip 10.96 kB); notice in `frontend/THIRD_PARTY_NOTICES.md`. | vitest adapter 6; 7 browser tests (sending/accepted/final, reduced + live toggle, failed import, hidden page, confirmed stop, completed-wins, stale view) | PASS functionally; performance gate pending T15 |
| T08 / F05, F07 | `ConversationInfo`: modeless 320px ≥1100, 420px modal tablet, full-width modal phone; log bounds/scrollTop unchanged; persistent-only manage actions (also with AI off); history/settings/memory links. Copy (plain rendered text, real clipboard result). Guarded New + "Dừng và mở mới" awaiting terminal + reconcile (cancelled / completed-wins / failed / unconfirmed). "Về tin mới" jump. Dialog `initialFocus`. Fixed receipts being wiped by the new-chat URL effect. | 12 browser tests RED → GREEN; chat-history specs updated by meaning (e2e + fullstack); screenshots `chat-info-{390,900,1280}-t08.png` | PASS (synthetic API) |
| T09 / F03, F09 | Settings in five named sections with per-section withdrawal and truthful resume paths; Voyage toggle "Giúp trợ lý tìm lại ghi nhớ liên quan" + on-demand disclosure; memory grouped (chờ duyệt / đã duyệt / đã xử lý); data dialogs cancel-first; "Tải bản sao dữ liệu". | 6 browser tests; full suite 118/118 | PASS |

Playwright `globalTimeout` raised 180 s → 600 s after the run silently skipped 46 tests at 3 min (no per-test timeout or assertion changed).

## Phases 6–9 — discovery, human chat, activities, personal journeys, accessibility (T10–T14)

| Task | Change | Evidence | Status |
|---|---|---|---|
| T10 | "Hồ sơ tìm bạn", "Hiển thị hồ sơ", "Gửi lời mời kết nối" (+ receipts only after server success); MATCH-off profile tab explains that review + Hiển thị hồ sơ re-grants (backend `social/routes.py`); unsaved-editor close guard (keep editing focused / save draft and close / discard; memory only); refused publish keeps preview and choices. | `social.spec.ts` 4 tests RED → GREEN | PASS |
| T11 / F16 | Human chat follows new messages only at the bottom or for own sends, otherwise "Về tin mới"; read marker only while the newest message is in view; "Chia sẻ và an toàn" header button → dialog with identity sharing, report, block and "Kết thúc kết nối" (nothing destructive next to Send; report remains after block/end). | 2 tests RED → GREEN; fullstack specs updated to the header control | PASS (synthetic) |
| T12 | Invitations say "tham gia", name focus plan/cycles from `timer`, "Từ chối lời mời"; dock wrapper ≤16px/220ms entrance (M16), reduced = in place; 160ms boundary colour on reveal/score/options; backend focus description without "máy chủ" jargon. | activities 2 RED → GREEN + reduced guard; backend activity tests 20/20 | PASS |
| T13 / F12, F15 | Voice transcript placement: "Đưa vào ô tin nhắn" (empty) or "Thêm vào tin nhắn" / "Thay nội dung" / "Giữ tin nhắn đang soạn"; 500-char limit explained, never truncated or sent. **Defect fixed:** stopping before audio arrived threw in `encodeWav` and the UI blamed the connection → now "Bản ghi quá ngắn…", no upload. Product sentence on sign-in/sign-up; private-profile counter; "Đã lưu cảm xúc ngày dd/mm/yyyy." | 6 tests (synthetic microphone through the real AudioWorklet path), 18/18 over 3 repeats | PASS (emulated mic) |
| T14 | **Defect fixed:** skip link hidden with a fixed −80px offset grew into view at 200% text and covered the header. Sweep: axe wcag2a/aa/21aa/22aa on 8 screens incl. open info surface at 390 and 1280 (0 violations); info modal↔modeless swap across 1100px; 44px button sweep; 200% text reflow. | 5 tests + skip-link guard | PASS (automated); manual AT BLOCKED |

## Phase 10 — copy catalog, performance, license, regression (T15)

### Microcopy catalog (758 entries; 220 replace decisions)

85 replacements were already resolved by T01–T14 rewrites. Of the 135 still matching source, 130 were applied in context (script reviewed per entry; short fragments only in named contexts), 4 with context-specific wording and 5 deferred:

| Entry | Decision | Reason |
|---|---|---|
| COPY-0065 | "Bạn có thể gửi lại lời mời cho hoạt động này sau ít phút." | proposal "đang tạm nghỉ" misdescribes a cooldown |
| COPY-0076 | "Tiếp tục hoạt động" | as proposed, applied in its dialog context |
| COPY-0429 | "Quyền riêng tư" | the control opens the privacy page; "Tùy chọn MoodPrint" would be vague |
| COPY-0569 | "Yêu cầu xem …" | fragment of a templated button |
| COPY-0301 | deferred | false positive — the duplicated "trong" was removed with the whole sentence in T03 |
| COPY-0403 | deferred | "Xóa dữ liệu đã chọn" would duplicate the trigger's accessible name |
| COPY-0416 | deferred | 03 fixes the nav label as "Trợ lý"; the "AI" tag marks every assistant |
| COPY-0535 | deferred | "Đăng nhập" as the sign-out section heading reads like a sign-in form |
| COPY-0685 | deferred | "Kết thúc kết nối" would duplicate its trigger's name in the stacked dialog |

User/model content, registry-only intro text and backend error codes were not rewritten.

### Paired production performance (17 V-MOTION-PERF)

Protocol: `frontend/tests/perf/motion-perf.mjs` — baseline build (`main@5872b72`) vs candidate build, served locally, synthetic API, Playwright Chromium headless, 390×844, CDP CPU throttle ×4, 1 warm-up + 11 alternating runs per arm. Arms: baseline; candidate; candidate with reduced motion; candidate with the orb chunk blocked. Raw samples kept in the local workspace JSON.

| Metric (median [min–max], ms unless noted) | Baseline | Candidate | Candidate, reduced motion |
|---|---|---|---|
| Click Gửi → sending status in DOM | 30.0 [25.6–56.5] | 27.8 [20.5–82.2] | 26.1 [21.0–35.3] |
| Final chunk received → reply bubble in DOM | 21.4 [15.2–90.2] | 19.1 [12.2–38.2] | 20.2 [14.8–46.5] |
| Nav click → destination heading | 210.4 [187.9–234.5] | 174.8 [149.2–203.1] | 181.0 [170.1–208.9] |
| CLS over the AI journey | 0.0094 | 0.0034 | 0.0034 |
| Canvas loops while accepted | 0 (GSAP dots, 61 rAF/s) | 1 orb (61 rAF/s) + GSAP ticker idling ≤120 frames after the 4px entrance | 0 |
| rAF after final | 0 | 0–14/s while GSAP auto-sleeps | 0 |
| Long tasks ≥50ms attributable to the orb chunk | — | 0 of 11 runs (separate 11-run attribution pass) | — |

Finding fixed during measurement: the status wrapper started a GSAP tween on every phase change, including the commit inserting the validated reply; the forced style read delayed the bubble (≈31 vs ≈19 ms). Now only the accepted entrance moves (14: sending is static); regression test in `motion.spec.ts` RED → GREEN. Baseline spread exceeds 10%, so per 17 the relative ≤10% gate is not decidable; the invariants (≤1 continuous loop, CLS ≤ 0.1, no attributable long task, no input/final gated on animation) hold, so **thinking-orbs 0.3.2 is retained**. Bundle: main JS 495.31 → 525.45 kB (gzip 160.73 → 168.82, of which ≈0.9 kB gzip is restored license comments); lazy orb chunk 26.41 kB (gzip 10.97); CSS 38.62 → 44.13 kB. No FPS or field-latency claim is made.

### Licenses

- GSAP standard license read 2026-10-27 at https://gsap.com/standard-license (effective 2025-04-30, modified 2025-05-30): free for websites/apps incl. commercial; prohibited for no-code visual animation builders competing with Webflow (not MoodPrint's case); proprietary notices must not be removed. **Pre-existing issue fixed:** minification stripped GSAP's `@license` header; `esbuild.legalComments: "inline"` keeps it.
- thinking-orbs 0.3.2: MIT, notice shipped in `frontend/public/THIRD_PARTY_NOTICES.md`.
- Not legal advice; owner review before distribution remains R02.

### Final verification (actual runs)

| Check | Result |
|---|---|
| `npm.cmd run typecheck` | exit 0 |
| `npm.cmd test` | exit 0 — 66/66 (baseline 54) |
| `npm.cmd run build` | exit 0 |
| `npm.cmd run test:e2e` | exit 0 — 146/146 (baseline 68). One earlier full run had 1 unreproduced failure in "hidden page…" while the backend suite ran concurrently; 59/59 on repeat |
| `uv run --locked ruff check app tests` | All checks passed |
| `uv run --locked mypy app` | no issues in 89 files |
| `uv run --locked pytest -q` (clean worktree of HEAD, disposable `moodprint_uxr_test`) | 620 passed, 3 failed — the same 3 fail on `main@5872b72`: they read `docs/plans/validation-artifacts/*.sql`, deleted by main's last commits. In the primary checkout 3 more fail only because the local `backend/.env` enables STT (pass in a clean checkout); `.env` was not read |
| `scripts/test_fullstack.py` (real FastAPI + PostgreSQL `moodprint_uxr_e2e_test` + Vite + Chromium, synthetic model/auth, provider keys blank, `_env_file=None`) | 28/28 passed after updating 6 stale wording assertions (first run 23/28, second 27/28 — every failure was an old copy fragment; behaviour was correct) |

### Final whole-branch review

Fresh reviewer: 0 Critical, 5 Important (all fixed with regression tests: preference reload on tab return reopening the default chat and aborting sends; reconcile dropping older pages; consent lost on abandoned send; phone focus to `<body>` after info child dialogs; info sheet stacking over a child dialog on resize), 7 Minor (deferred, listed in the handoff).

## Traceability review (13)

| Finding | Task | Verification | Implemented | Evidence | Status |
|---|---|---|---|---|---|
| F01 starter auto-send | T01 | V-SEND-INTENT | yes | 4 tests RED→GREEN (no consent/message write; caret insert; 500-char; IME/Shift+Enter/double activation) | PASS |
| F02 activity failures invisible | T02 | V-ACTIVITY-ERROR | yes | catalog 503 retry, invite 503 in dialog keeps plan + same Idempotency-Key, 429 per kind | PASS |
| F03 consent recovery to nonexistent controls | T03/T09/T10 | V-CONSENT-COPY | yes | AI→Send, MEM→approve, MATCH→Hiển thị hồ sơ (backend grant paths verified); Settings offers no enable toggles | PASS |
| F04 blocking promise | T03/T11 | V-BLOCK-TRUTH | yes | both entry points "không thể hoàn tác trong ứng dụng", cancel-first, report independent | PASS |
| F05 run exit ambiguity | T08 | V-RUN-EXIT | yes | New disabled pre-acceptance; stop-and-new waits for terminal + reconcile; completed-wins; failed stop keeps view; no replay | PASS (synthetic SSE) |
| F06 final-only contract | T07 | V-AI-STATUS | yes | adapter 6 unit tests; 7 browser tests; stream validation unchanged | PASS |
| F07 chat control density | T08 | V-INFO-PANEL / V-HISTORY | yes | 320/modal/420/modeless geometry, transcript bounds/scroll unchanged, persistent-only actions incl. AI off | PASS |
| F08 tiny type | T04 | V-TOKENS / V-REFLOW | yes | computed sizes at 6 widths, 44px sweep, 200% text | PASS (emulated) |
| F09 privacy jargon | T03/T09 | V-PRIVACY-COPY | yes | plain Voyage label + on-demand disclosure with recipient/scope/deletion | PASS |
| F10 hidden mood entry | T05 | V-NAV | yes | five destinations at 320/768/1280, direct /self | PASS |
| F11 service errors blame input | T03 | V-SERVICE-ERROR | yes | client unit tests + non-JSON 500 browser test | PASS |
| F12 voice overwrite | T13 | V-VOICE-DRAFT | yes | append/replace/keep, empty-recording defect fixed | PASS (emulated mic) |
| F13 export recovery | T03/T15 | V-EXPORT | copy only | backend test RED→GREEN; paged export not built (R06) | PARTIAL — product/API decision |
| F14 route focus | T05/T14 | V-ROUTE-FOCUS | yes | visible conversation heading at 390/1280; no focus steal | PASS |
| F15 auth orientation | T13 | V-AUTH | yes | one-sentence product description, form remains in viewport | PASS |
| F16 safety hierarchy | T11 | V-SAFETY | yes | header dialog; nothing destructive in the composer | PASS |

Motion inventory (16): M01–M05 CSS state tokens; M06 dialog 8px/220ms; M07 CSS backdrop; M08/M09 info panel 24px/16px 260ms (exit immediate — accepted fallback in 15); M10 accepted entrance only (≤4px/160ms); M11 one lazy orb; M12 reply rendered immediately; M13–M15 text/receipt state with CSS feedback; M14 "Về tin mới" explicit smooth scroll (instant under reduced); M16 dock ≤16px/220ms; M17–M19 160ms boundary colour, scores/timers instant; M20–M22 CSS state only. Omissions honoured: no ScrollTrigger/ScrollSmoother/Flip, no clearProps:"all", no killAll, no stagger, no count-up/confetti/shake.

## Blocked / not run (not PASS)

| Check | Status | Why |
|---|---|---|
| NVDA/VoiceOver, physical iOS/Android keyboards and safe areas, real browser 400% zoom, forced colors | BLOCKED | no assistive technology or devices in this environment; automated axe + emulated widths/200% text only |
| Real microphone / provider transcription, real AI provider, real Supabase email flows | NOT RUN | synthetic fixtures only; no paid or live calls were authorised |
| Firefox / WebKit | NOT RUN | only Chromium is provisioned for this repo's Playwright config |
| Field performance (INP/LCP), real mobile hardware | NOT RUN | local paired lab measurement only |
| R06 large-export recovery | PARTIAL | needs a product/API decision; copy no longer promises a missing action |
| R04 Node 24 local vs Node 22 CI | NOT RUN | CI not executed from here |

## Hands-on check in a real browser against the real stack

Requested after the automated runs: the real backend (`tests.e2e_server`: real FastAPI, PostgreSQL `moodprint_uxr_manual_test`, Supabase auth stub, synthetic SDK model, no provider keys) and the real Vite frontend, driven with agent-browser 0.39.4 (Chromium). Synthetic account `local-mvp-45` signed in through the real login form. No hosted/production system, real account or paid API was used.

| Step (width) | Observed |
|---|---|
| Login (390) | One-sentence product description; real auth round-trip to the assistants list |
| Choose Mây (390) | Focus on visible heading "Mây AI" (F14) |
| Starter chip | Draft filled, composer focused, nothing sent (F01) |
| Gửi | "Đang gửi tin nhắn…", no canvas before acceptance; synthetic reply rendered, status cleared (accepted phase too fast to sample with the synthetic model) |
| Sao chép | real clipboard write → "Đã sao chép câu trả lời." |
| Info (390) | full-width modal sheet, heading focused; temporary thread shows "Tạm thời" + temporary disclosure, no rename/download/delete; Escape returns focus to the trigger |
| Cảm xúc nav | `/self`, heading focused; save → "Đã lưu cảm xúc ngày 27/10/2026." from the real API |
| Settings (1280) | five sections; enabling history → "Đã lưu lựa chọn của bạn." |
| Saved chat (1280) | header "Đã lưu"; info is a 320px modeless region with Đổi tên / Tải xuống / Xóa; rename field focused + selected, real PATCH, receipt, focus back to "Đổi tên", history list shows the new name |

Screenshots and raw logs are kept locally in `docs/ux-redesign/evidence/implementation/` (git-ignored, like the rest of `evidence/`).
