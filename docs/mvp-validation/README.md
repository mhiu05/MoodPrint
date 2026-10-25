# MVP completion — mood, matching, human chat, consent/privacy, frontend

Validation record for the 25 Oct 2026 MVP-completion pass. Every result below was
produced by a command run in this pass; older reports are not reused as evidence.
Deployment was out of scope and was not attempted.

## What changed

### Mood tracking and self-insight
- **Day boundaries follow the account timezone.** `PUT /moods/{date}` used to validate "future"/"expired" against the client's timezone, while list, summary, export, retention and the Nhịp scope all use `user.timezone`. Now all of them use the account timezone, and `mood.timezone` is stored from it.
- **Notes** are trimmed before the 120-character check.
- **`GET /moods/summary`** now accepts an optional inclusive `from`/`to` range (inside the 90-day window; anything else returns `422 INVALID_RANGE`) and returns `min`/`max`.
- **Missing days stay `null`** in the summary and are never imputed. The response is a typed `MoodSummaryDTO`.
- **New UI module** `frontend/src/features/real/Mood.tsx`:
  - choosing a day that already has an entry loads it into an explicit edit mode (fixes silent overwrites);
  - delete asks for confirmation in a dialog;
  - date picker min/max cover the 90-day window, and "today" follows the server clock and midnight;
  - inputs stay disabled until the saved list loads, so typed text cannot be wiped by the load;
  - a `409` refetches and keeps the typed input;
  - history is shown newest-first;
  - an insights panel offers 7/30/90 days, an accessible chart with a data table, a "not enough data" state, and non-clinical copy.

### Matching and connections
- **Private-profile edits no longer unpublish the matching profile or close rooms.** Private items are never matching sources.
- **`GET /profiles/published/current`** reports `state: live | needs_republish` and the `profileVersion` that withdraw/publish expect. Before this, a profile made stale by a consent revoke/restore showed as "shared" and could never be withdrawn (permanent 409). The UI now says "Hồ sơ đang tạm ẩn" and never republishes implicitly.
- **Sending back to someone who already invited you** completes the match even at the daily invitation quota, the same as accept.
- **Discovery** is bounded (scan cap and a 10-peer shortlist). Peers who fail the locked recheck are replaced, so the list still fills to 5.
- **Expired candidate/safety references** are purged by the retention job.
- **Polled reads take no row locks:** connection view, message pages and reveal listing.

### Human chat and safety
- **Event stream:**
  - The UI resumes the stream from the newest `seq` and reconnects with backoff.
  - HTTP polling is now a fallback: every 3s while the stream is down, every 15s while it is healthy.
  - Server-side, an open stream reads one cheap `(next_seq, version, status)` row per second. The full live-policy check runs on any change, before every announcement, and at least every 5s.
- **When access is lost** (block, end, MATCH withdrawal, peer deletion), a stale tab stops polling, disables the composer, clears the peer's messages and says why. Sends from it are rejected by the server.
- **Reporting after blocking or ending:**
  - Evidence may come from any of the pair's rooms within 90 days; a live room is no longer required.
  - The person who blocked or ended keeps a report-only panel with the messages they had already seen.
  - Report references must not be expired, and reports are limited to 5 per user per day.
- **Confirmations:** blocking from a discovery card and ending a connection now ask first.
- **Lists:** the `/messages` list refreshes every 15s, and request states are labelled precisely.

### Consent, privacy and data lifecycle
- **Settings copy:**
  - Corrected the MEM text: memory needs AI, it is not "independent".
  - Each permission now states what turning it off stops, keeps and deletes, matching `consent/routes.py`.
- **Export** gains two sections:
  - `consents`: current state and change history;
  - `social`: matching draft and published versions, own identity fields, own request/connection metadata, own sent messages (peer shown only by pseudonymous alias), reports filed (reason/status/evidence count; never the quoted peer text), blocks made, and identity-sharing state.
  
  The existing caps (1,000 rows per type, 2 MB, one use, same session, 15 minutes) still apply.
- **Account-deletion dialog** states what is retained (reports filed, consent history, a name/email-free tombstone) and that provider backups are not covered.
- **API client:** an idempotency intent is dropped after a definite 4xx rejection. Previously, rejected writes accumulated toward the 50-pending limit.

### Frontend and mobile
- On mobile, `/chat/:id` is a full-screen conversation like the AI chat: the bottom nav is hidden and the chat has its own back button.
- The message log is capped to the visual viewport (`--app-height`), so the newest message and the composer stay visible together with the keyboard open.
- The mood average no longer wraps, and the per-day table uses the full width.

## Commands run and results

### Backend, against local PostgreSQL 17 + pgvector on :16432 (`*_test` databases)

| Check | Result |
|---|---|
| `uv run ruff check app tests evals alembic <CI scripts> ../scripts/load_social_mood.py ../scripts/test_fullstack.py` | PASS |
| `uv run mypy app` | PASS (61 files) |
| `uv run pytest -q` | 278 passed, 0 skipped, 0 failed |
| `alembic upgrade head` and `alembic check` on a fresh DB | PASS: head `0010_account_deletion`, no drift |

New tests:
- `tests/test_mood.py` (8)
- `tests/test_matching_lifecycle.py` (14)
- `tests/test_privacy_lifecycle.py` (9)
- 1 added to `tests/test_notifications.py`

Red/green was confirmed by restoring the single source file to HEAD: account-timezone boundaries (`mood/routes.py`), private edits keeping the profile live (`profiles/routes.py`), report after block (`moderation/routes.py`), social export (`users/routes.py`) and the client intent tests (`api/client.ts`). Each fails on HEAD and passes with the fix.

### Frontend

| Check | Result |
|---|---|
| `npm run typecheck` | PASS |
| `npx vitest run` | 89/89 (adds `src/api/client.test.ts`; 2 of its 3 cases fail without the fix) |
| `npm run build` | PASS |
| `npx playwright test tests/e2e` (mocked API) | 34/34 |

### Full stack: real FastAPI + PostgreSQL + Vite + Chromium (`scripts/test_fullstack.py`)

All 13 specs pass, including the new `tests/fullstack/mvp.spec.ts`:

| Journey | Covered |
|---|---|
| E | Export contains only the owner's data; one download |
| Mood | Create → reload → edit → stale-tab conflict → insights 7/30 → keyboard-only delete dialog (focus trap, Escape, focus restore) → reload |
| B/C | Two users publish in the UI → discover → request → accept → chat (double-click sends one message) → reload both → user C gets 404 on read/send → B withdraws MATCH and A's open tab closes without reload (composer disabled, API send 403) → re-enabling shows "tạm ẩn" and no republish |
| D | Block → the blocker reports with evidence after the block → the peer's stale tab closes → peer send 403 → no rediscovery. End requires confirmation (Escape keeps the room) → peer read 403 |
| F | 390px and 430px (touch): mood, discovery, messages and chat with no horizontal overflow. In a 390×480 "keyboard" viewport the composer and the newest message are both on screen, the send target is ≥44px and the nav is hidden |
| a11y | 7 real screens × 1440/1280/430/390 with reduced motion: axe `wcag2a/aa/21aa` shows 0 violations and there is no horizontal overflow |

Screenshots at 1440/390 and the mobile chat views are in [`screens/`](screens/).

### Hosted Supabase (project `roznanxbiyqybjpvtilq`, synthetic fixtures A/B, `scripts/test_supabase_fullstack.py`)

| Suite | Result | Notes |
|---|---|---|
| `--suite core --reset-fixture-pair` | 2/2 PASS | Login UI; age gates; cross-user private denial; mood/private reload; SDK-fake memory proposal → owner approval; publish; simultaneous mutual requests → one room; chat and duplicate dedupe; real backend PID restart; reveal grant/revoke; report; block → both directions 403; provider session revoke; logout and old-cookie denial. New: hosted mood create/reload/edit/summary/confirmed delete, and MATCH off → on giving `needs_republish` and candidates 403 until an explicit republish |
| `--suite scoped` | 1/1 PASS | Nhịp reads only the selected mood dates and never notes |

The first core attempt failed: an A/B room left open by an earlier session was closed when the test republished A, which set a 30-day cooldown (by design). The second attempt exposed a test race (probing before the UI block request returned); the spec now waits for the "Bạn đã chặn" banner. The block itself was confirmed in the hosted DB. The third attempt passed. The hosted schema remains at `0010_account_deletion` and no DDL was run. Security advisors show only the existing Auth WARN.

### Live OpenAI (real provider, `scripts/run_live_browser.py` with `evals.server`)

| Spec | Result |
|---|---|
| Journey A: five companions, Nhịp scoped mood tool (notes excluded), Gương memory proposal → explicit approval, peer cannot confirm | PASS (2.0 min) |
| Provider cancel, duplicate intent and AI consent revoke suppress late output | PASS (31 s) |

## Performance (single uvicorn worker, production pool 8+4, local PostgreSQL)

Harness: [`scripts/load_social_mood.py`](../../scripts/load_social_mood.py), synthetic users only, no provider calls.

**Workload per user:**
- 5 mood writes, a retried edit, list and 30-day summary;
- MATCH consent, draft, preview and publish;
- discovery;
- mutual request (half the pairs race reciprocal sends) and accept;
- an event stream held open while 10 messages are sent (every third one double-submitted) with cursor polling;
- a cross-pair access probe;
- AI consent toggles.

**Checked:** HTTP statuses, duplicate or missing sequence numbers, foreign-room leaks, the expected number of rooms, and pool use.

| Users | Think | Requests | req/s | Unexpected HTTP | Integrity failures | Rooms | Pool peak | mood_put p50/p95 ms | mood_summary p50/p95 ms | publish p50/p95 ms | candidates p50/p95 ms | request_send p50/p95 ms | message_send p50/p95 ms | message_poll p50/p95 ms | history p50/p95 ms | consent p50/p95 ms | events_first p50/p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [5](load-social-5.json) | 0 | 196 | 41.0 | 0 | 0 | 2/2 | 8/12 | 52/58 | 33/36 | 60/65 | 213/288 | 80/161 | 104/417 | 60/136 | 63/66 | 87/90 | 247/266 |
| [10](load-social-10.json) | 0 | 457 | 51.4 | 0 | 0 | 5/5 | 12/12 | 110/132 | 71/76 | 115/126 | 533/841 | 101/678 | 188/465 | 137/209 | 232/272 | 179/194 | 675/748 |
| [20](load-social-20.json) | 0 | 911 | 51.5 | 0 | 0 | 10/10 | 12/12 | 189/269 | 147/185 | 224/253 | 824/1468 | 229/1144 | 424/699 | 359/598 | 358/499 | 339/437 | 1085/1415 |
| [50](load-social-50.json) | 0 | 2274 | 53.8 | 0 | 0 | 25/25 | 12/12 | 471/882 | 410/693 | 281/640 | 1582/2970 | 1047/1704 | 1063/2054 | 1052/1949 | 722/1135 | 578/1025 | 2536/3595 |
| [50](load-social-50-think1s.json) | 1s | 2273 | 31.6 | 0 | 0 | 25/25 | 12/12 | 34/61 | 37/327 | 45/85 | 819/1601 | 113/707 | 327/624 | 277/571 | 49/140 | 67/384 | 965/1728 |

Zero think time is a worst-case burst: every user acts at once. Throughput tops out at about 50 requests/s on this Windows host. That is the CPU limit of one Python worker, with the driver sharing the same machine, and is consistent with the earlier chat-load results. With a realistic randomised 1s think time, 50 concurrent users see p95 ≤ 0.71s for mood, profile, request and message operations, with no errors or integrity failures. The slowest operations at that pace are discovery (p95 1.6s; locked recheck of up to 10 peers) and the first stream event (p95 1.7s, which includes the 1s polling cadence). In 1 of 3 zero-think 50-user bursts, one request failed client-side with an httpx `ReadError` (a dropped connection, no HTTP error, flow aborted); that report is kept as [`load-social-50-run1-readerror.json`](load-social-50-run1-readerror.json). The harness now reports and retries such transport errors once with the same idempotency key, and two further bursts recorded none.

The event-stream change was measured A/B with 50 open streams and 1s think time:
- message send p50 359 → 273 ms, p95 661 → 549 ms;
- message poll p50 289 → 220 ms.

## Remaining limits (verified, not fixed here)
- **Saved AI replies are not rewritten** when moods are deleted, though they can be deleted per conversation. Saved AI conversations are exported per thread, not in the account export.
- **Blocks are permanent**: there is no unblock, by product choice.
- **Messages a deleted user sent become "[Đã xóa]"**, so report evidence quoting them loses that text.
- **Provider and backup erasure is not verified.** Supabase leaked-password protection is still off (WARN; needs a paid plan).
- **Not run:**
  - real-device iOS/Android keyboard behaviour (only approximated by viewport);
  - screen readers (only automated axe checks);
  - 200% zoom.
- **Single process by design:** temporary AI chats, exports, rate limits and stream slots are in-process.
