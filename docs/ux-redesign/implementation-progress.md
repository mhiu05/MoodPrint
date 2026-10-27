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
