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
