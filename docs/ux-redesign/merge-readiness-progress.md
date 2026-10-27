# Merge-readiness progress (feat/ux-redesign)

Working log for fixing the confirmed review defects MR01–MR11 and the CI prerequisites. The original audit (`implementation-progress.md`) is untouched. Local, synthetic work only: no push, merge, deployment, hosted database, paid model or remote CI.

## S0 — Baseline

| Item | Value |
|---|---|
| Branch | `feat/ux-redesign` (unchanged; not switched) |
| Start HEAD | `a38ec15a07382095cf09bded1b6290ee551bf076` |
| Merge-base with `main` | `5872b72466522944931d694e99116e5f733c3a8a` |
| Pre-existing local changes (left alone, never staged) | ` M .gitignore`; untracked `docs/ux-redesign/00…18, 99, 100*.md`; untracked `frontend/evidence/` |
| Tooling | Node/npm with Playwright 1.56 + installed Chromium; `uv` pinned Python 3.12; Docker PostgreSQL 17 + pgvector on `127.0.0.1:16432` |
| Browser servers | The developer's Vite on 5173 is never reused. `frontend/playwright.owned.config.ts` (untracked, local helper) starts an owned Vite on 5190 with `reuseExistingServer:false` and an API proxy to unused 59998; every API call in these specs is intercepted |
| Test DB | New disposable `moodprint_mr_test` on the local container (name ends `_test`, loopback, guarded by `tests/database_target.py`); no existing database dropped or reused |

Newline note: pre-existing files are CRLF in the working tree (`core.autocrlf=true`, index LF); new files are LF.

## Method

Each task: failing regression first (RED, captured under `evidence/implementation/merge-readiness/`), smallest fix, targeted run, full-suite run, scoped commit. Races use deferred (gated) responses, never sleeps; React's scheduler is held explicitly for MR04.

## Task tracker

| ID | Origin | Result | Regression | RED → GREEN evidence |
|---|---|---|---|---|
| MR01 starter overwrites human-chat draft | introduced | fixed | `merge-readiness.spec.ts` ×5 + `draftInsert.test.ts` ×7 | `red-1.txt` → `green-2.txt` |
| MR02 acceptance erases newer edits (AI + human chat) | pre-existing | fixed | ×6 (edit during POST, edit back to same text, rejected POST + same idempotency key, double submit, unedited clears, human receipt) | `red-1.txt` → `green-2.txt` |
| MR03 resumed failure restores another chat's text | pre-existing | fixed | ×3 (cross-chat, matching restore, newer edit wins) + switch-before-failure | `red-1.txt` → `green-2.txt` |
| MR04 Send right after New aborted | pre-existing | fixed | ×3 (scheduler held; genuine failure keeps draft; real navigation still aborts) | `red-1.txt` → `green-2.txt` |
| MR05 run completes while New confirmation open | introduced | fixed | ×2 (completed → New with completed-first receipt; unknown outcome keeps view) | `red-1.txt` → `green-2.txt` |
| MR06 New while ordinary Stop pending | introduced | fixed | ×2 (one cancel, one New; failed cancel keeps thread/draft) | `red-1.txt` → `green-2.txt` |
| MR07 failed cancel refresh allows Send | introduced | fixed | ×2 (blocked until retry succeeds; retry reattaches active run without message POST) | `red-1.txt` → `green-2.txt` |
| MR08 conversation-scoped notices | introduced | fixed | ×3 (selection, New, receipt survives one URL change only) | `red-1.txt` → `green-2.txt` |
| MR09 ambiguous invitation wording | pre-existing | fixed | ×3 (committed-but-lost 503, dropped connection, 4xx keeps server text); retry creates one invitation with the same Idempotency-Key | `red-2.txt` → `green-3.txt` |
| MR10 shared pending label | pre-existing | fixed | ×1 | `red-2.txt` → `green-3.txt` |
| MR11 dangling `aria-controls` | introduced (panel) / pre-existing (discovery tabs) | fixed | ×5 (closed, phone child dialog, resize while child dialog open, Escape, discovery tabs) | `red-2.txt` → `green-3.txt` |
| CI-1/2/3 three backend tests | pre-existing (deleted `docs/`) | fixed | existing tests now pass on real PostgreSQL | `red-ci.txt` (paths absent at a38ec15) → `backend-clean-checkout.txt` |
| CI-4 `check_plans.py` | pre-existing | replaced | `backend/tests/test_reviewed_artifacts.py` ×19 | `red-ci.txt` (paths absent at a38ec15) → `backend-clean-checkout.txt` |
| Cosmetic EOF blanks (`focusHeading.ts`, `ux-fixtures.ts`) | introduced | fixed | `git diff --check` | final gates |

### What changed and why (summary)

- **Drafts.** `draftRevision` counts edits; a message acceptance clears the draft only if no edit happened since the submit (AI and human chat). Starter insertion is the shared pure `insertAtSelection` (caret/selection aware, 500-char guard, no truncation). Human chat gains the same advisory notice.
- **Recovery ownership.** `recovery` binds restored text to conversation + request key + view generation + the revision at which the draft was emptied. `viewGeneration` bumps on real selection, New and unmount; canonical-URL updates after a first send do not bump it.
- **New / Stop / reconciliation.** `newMarker` makes the router applying a New URL a no-op for the fresh lifetime (MR04). `confirmTarget` + `settled` re-evaluate a New confirmation from the validated, reconciled outcome of that exact run (MR05). `cancel()` returns `accepted | pending | failed` and `cancelRequested` lets New reuse a Stop already in flight (MR06). A failed post-cancel read sets `ready=false`; the existing Retry reloads and reattaches an active run (MR07).
- **Presentation.** Notices, draft notice, manage errors and the confirmation are reset on selection/New; the stop-and-new receipt is simply not touched by the New URL transition and is cleared by any later selection. Invite failure wording distinguishes unconfirmed (5xx/network) from refused (4xx). `pendingInvite` labels only the kind being sent. The info trigger's `aria-controls` is present only while the panel is mounted; discovery tabs reference only the rendered panel.
- **A regression I introduced and fixed during MR11.** A second `useMedia` subscription inside `ConversationInfo` could disagree with the first for one frame and stack the modal info sheet over an open rename dialog. The existing test `narrowing the window while a rename dialog is open…` caught it; one subscription now decides both.

### CI prerequisites

- **Provenance (read-only Git).** `docs/` was deleted in `41e27c7` ("chore: delete documents", in `main` and in this branch). The approved SQL was last recorded in its parent `5e73a130fd0f081887c3c2ab2093c43674388012`.
- **Recovered unchanged** into `deploy/supabase/reviewed-sql/` (byte-compared against the blobs; sizes/hashes in `MANIFEST.json`, newline conversion disabled by `.gitattributes`):

| File | SHA256 |
|---|---|
| supabase-initialization-review.sql | 7180c9e12748af574599a6fe56240643d57d877dd906a51d6dd9923262d9173e |
| supabase-initialization-auth-review.sql | e6448c3a9684edb4c81f883f5e8c6681ede5a13a596699436a396b465975f872 |
| supabase-runtime-login-review.sql | d9124bfd7747a7a04841b8e471a38ddfe6de04d87f91b20ffd63e3f79a1f0461 |
| supabase-0006-0009-review.sql | 289b67aab763849c776893425b2fc92b498e79118442003318f9192e5df01121 |
| supabase-0010-review.sql | b9fe14aa75e84ad435d052c206fdb75b4e0d53af10d9f2028255f87bd4f2419e |
| 0011-review.sql | b12f30efdd01777caf200865d5b8052525c12ea007ecbc91616d5a8dafd8a082 |
| 0012-review.sql | 59c37353a13bb6b747a4be2705d341107443c8639847f63efb040c046a141cee |
| 0013-review.sql | eb3e73df3a9314f608f3e9267c008f0166a840a5e132fcd6e7454ffe1751e9f5 |
| 0014-review.sql | 0678298210accc2916331b979656a15052e388c65a88f00a557647cfaac6e3c4 |

- **Not restored (deliberately):** the rest of `docs/plans` (documents, execution reports, JSON evidence, credentials-adjacent artifacts), `0006-ai-usage-review.sql` under `live-ai/`, `supabase-migrations-0001-0005.sql`, and `docs/ai-context-privacy-p0/0015-review.sql` — no script or test consumes them.
- **Not authorization.** Hash approval (`--approved-sha256`), target/project/TLS/role checks, wrong-hash refusal before any subprocess/connection, least-privilege role SQL and explicit apply approval are unchanged. Nothing was applied to any hosted system.
- **Legacy plan check retired.** `scripts/check_plans.py` validated the deleted `docs/plans` and cannot pass without them. CI now runs `scripts/check_reviewed_artifacts.py`: non-empty manifest, every file present and byte-identical, no unlisted SQL in the pinned directory, no script pointing at `docs/` or an unpinned file, no orphan approval. Positive and negative tests: `backend/tests/test_reviewed_artifacts.py`, which also re-checks every upgrade approval against Alembic's offline export.
- **Latent bug fixed on the way.** The initialization approvals were compared with `alembic upgrade head`, which can never match once 0006+ exist; they are now compared with the `0005_export_scope` export they were generated from (the new test is the RED→GREEN).
- Still referencing `docs/plans` but not CI-gated and not touched: `scripts/collect_implementation_checks.py` (legacy evidence collector), README links to `docs/plans/implementation-status.md`.

## Final verification

Candidate commits: code tree `b458b62` (all UI/CI changes), then `1f7c35c` (one-line test hardening), then this document. Everything below ran locally against disposable synthetic targets (PostgreSQL `moodprint_mr_*_test` on `127.0.0.1:16432`, fake SDK model, Playwright with intercepted APIs). Raw output is under `docs/ux-redesign/evidence/implementation/merge-readiness/` (Git-ignored like the rest of `evidence/`).

| Check | Command (from) | Result | Evidence |
|---|---|---|---|
| Typecheck | `npm.cmd run typecheck` (frontend) | PASS, exit 0 | `frontend-final.txt` |
| Unit tests | `npm.cmd test` | PASS, 73/73 in 13 files (was 66) | `frontend-final.txt` |
| Build | `npm.cmd run build` | PASS, exit 0 (existing >500 kB main-chunk warning unchanged) | `frontend-final.txt` |
| Browser E2E, whole suite | `playwright test -c playwright.owned.config.ts` (owned Vite 5190) | PASS, 183/183, exit 0, 0 skipped, 0 flaky (was 146 + 37 new) | `e2e-after-s3.txt` |
| E2E of the new spec alone | same, `merge-readiness.spec.ts` | PASS, 37/37 | `green-3.txt` |
| Full-stack (real FastAPI + Vite 5174, PostgreSQL, SDK fake model) | `uv run --locked python ../scripts/test_fullstack.py` (backend) | PASS, 28/28, exit 0 | `fullstack-final.txt` |
| `npm audit --audit-level=low` | frontend | PASS, 0 vulnerabilities | `npm-audit.txt` |
| Contract generation + drift | `export_openapi.py`, `npm run contracts:generate`, `git diff --exit-code` | PASS, no drift | `contract-drift.txt` |
| Ruff (CI scope incl. new script) | `uv run --locked ruff check app tests evals alembic ../scripts/…` | PASS | `backend-final.txt`, `backend-clean-checkout.txt` |
| Mypy | `uv run --locked mypy app` | PASS, 89 files | same |
| Backend suite, clean checkout of `b458b62` (no `.env`) | `uv run --locked pytest -q` | PASS, 642 passed, 0 failed, 0 skipped, 940 s | `backend-clean-checkout.txt` |
| Backend suite, clean checkout of `1f7c35c` | same | PASS, 642 passed, 0 failed, 0 skipped, 901 s | `backend-final-sha.txt` |
| Backend suite, developer working tree before the conftest fix | same | 639 passed, **3 failed** — local `.env` contamination (`STT_ENABLED`), pre-existing and unrelated to the changes; same tests pass in a clean checkout and, after `1f7c35c`, here | `backend-final.txt` |
| Reviewed-SQL integrity | `python scripts/check_reviewed_artifacts.py` (clean checkout, no untracked files) | PASS, 9 pinned / 9 consumed | `backend-final-sha.txt` |
| Alembic chain on a fresh DB | `alembic upgrade head`, `alembic check` | PASS, "No new upgrade operations detected" | `alembic-chain.txt` |
| AWS release poller tests | `python -m unittest discover -s deploy/aws/tests` | Windows: BLOCKED (`fcntl` is POSIX-only). In the local Linux image `moodprint-api:ci`: PASS, 14 tests | `aws-tests.txt`, `aws-tests-linux.txt` |
| `git diff --check 5872b72..HEAD` | repo root | PASS, no output | — |
| Remote CI for the exact SHA | `gh run list --branch feat/ux-redesign` | NOT RUN — branch not pushed, no runs exist | — |
| actionlint, Docker/Compose packaging builds, load harnesses (`load_chat_memory`, `load_social_mood`) | CI-only steps | NOT RUN — heavy or need an unpulled image; untouched by these changes | — |
| Performance re-measurement | — | NOT RUN — no change touches the measured motion path. Prior caveat stands: the relative-10% gate was inconclusive and "equal or faster everywhere" was never proved | — |

Isolated environment: the checkout-with-`.env` result above is shown, not hidden. The decisive runs use a throw-away `git worktree` of the exact commit (removed afterwards) so no ignored or untracked local file can influence them. The same worktree also proves the CI integrity check needs nothing but tracked files, and that the byte-pinned SQL keeps its hashes under this machine's `core.autocrlf=true`.

## Remaining limitations (not claimed as verified)

- **Remote CI** has not run for any of these commits (nothing is pushed). Local passes are not a remote pass.
- Physical devices, NVDA/VoiceOver, Firefox/WebKit, real browser zoom/forced colors: not tested; widths were emulated in Chromium only.
- Real providers, microphone/STT, hosted Supabase: not exercised (synthetic fixtures only). Nothing recovered under `deploy/supabase/reviewed-sql/` was applied anywhere; each still needs its own explicit `--approved-sha256` approval.
- The 28 + 9 new browser specs intercept the API; MR-level races are therefore proven against the real frontend state machine, not against real server timing. The full-stack suite covers the ordinary journeys only.
- IME composition is covered only by the existing `isComposing` Enter test; Shift+Enter and rapid double submit are covered; reduced motion and StrictMode are covered by the existing suites that ran green (StrictMode is the dev-server default for these runs).
- `scripts/collect_implementation_checks.py` and two README links still point at the deleted `docs/plans`; not CI-gated, left for a docs decision.
- Retention of `frontend/playwright.owned.config.ts`: untracked local helper (copy kept in the evidence folder); commit it only if the owner wants a documented isolated-server config.

**Overall status: PARTIAL** — every local gate passes, but required remote CI for the exact SHA is NOT RUN and device/AT coverage is outstanding. This is not a merge approval; the branch is unpushed, unmerged and nothing was deployed.

## Continuation — canonical first-send URL vs Back (review of `c1599c6`)

The review of `c1599c6` reproduced one remaining P2 (twice, Chromium, gated synthetic API and held scheduler): A open, New with React's scheduler held, an immediate send, and C created **and** accepted before the scheduler is released. C's canonical `?conversation=C` then commits together with New's held render. The same-view early return in the selection effect kept `openedFor` at A's key (and the New marker unconsumed), so Back to A matched that stale key and was skipped. The URL named A while C's message and working status stayed on screen, and A was not read again. Its precise historical origin is not established. This is a frontend selection race, not a proven cross-user backend disclosure.

- **Fix** (`frontend/src/features/real/RealApp.tsx`, selection effect): when the canonical URL applies to the thread already on screen while a New marker is still pending, the marker becomes the opened key, just as if the marker URL had applied first. The early return is otherwise unchanged: no abort, and no change to view generation, draft, recovery or `loadedSelection`. A later Back or selection is a real selection again: it bumps the generation, aborts C's UI reader (a local abort, not a server cancel) and loads A. The normal order is untouched; the fast order now ends in the same bookkeeping state.
- **Regression** `merge-readiness.spec.ts`: `MR04: a fast canonical first-send URL still lets Back select the previous chat (late completed | late failed)`. It reuses `mount`, the gates and `holdScheduler` and asserts:
  - Creation and acceptance finish before release, with held work still pending.
  - One conversation POST and one message POST; the reader is not aborted by canonicalisation.
  - C's message and status render under C's URL.
  - Back: A's URL and transcript, more reads of A than before Back, C's reader aborted, C's content and status absent, route heading focused.
  - C's delayed terminal released after Back: A's transcript, draft, status, alerts and focus are unchanged.
  - Forward rebuilds C from its stored transcript with no additional message POST or events stream.
  - No page errors.

  The original MR04 order (release before creation) stays and passes.
- **Evidence** (Git-ignored): `docs/ux-redesign/evidence/implementation/merge-readiness/canonical-back-fix-20261027/`, run on an owned Vite on 5191 with `reuseExistingServer:false` and the API proxy on unused 59997.

| Check | Result | Evidence |
|---|---|---|
| New regression before the fix | RED, 2/2 failed at the post-Back transcript assertion: received `Tin riêng của cuộc trò chuyện mới` under A's URL; every pre-Back assertion passed | `red.txt` |
| `merge-readiness.spec.ts` after the fix | PASS, 39/39 | `green.txt` |
| MR04–MR07 `--repeat-each 10` | PASS, 110/110 | `repeat-mr04.txt` |
| `npm.cmd run typecheck` | PASS, exit 0 | `typecheck.txt` |
| `npm.cmd test` | PASS, 73/73 in 13 files | `unit.txt` |
| `npm.cmd run build` | PASS (existing >500 kB chunk warning) | `build.txt` |
| Full configured E2E (`playwright.config.ts` testMatch, owned server) | PASS, 185/185, 0 skipped, 0 flaky | `e2e-full.txt`, `results-full.json` |
| `python scripts/check_reviewed_artifacts.py` | PASS, 9 pinned / 9 consumed | `reviewed-sql.txt` |
| `git diff --check 5872b72` (tracked changes) | PASS | — |

Remaining (not fixed, lower severity): choosing the *same* previous chat again while New's own transition is still held leaves the effect's dependencies unchanged. The URL can then name A while the fresh New view stays empty. No other conversation's content or run is involved, and it needs a held scheduler like the race above. Backend, full-stack, packaging and actionlint are left to remote CI for this candidate; the frontend change touches no backend, API or schema.

### First remote CI for the branch (`ee67707`) and its two failures

PR #19 started the first remote `Verify local application` runs for this branch. Both runs passed the backend and migration/load steps and failed in "Frontend and contract drift". The later steps did not run.

| Test | Runs | Root cause | Fix | RED → GREEN |
|---|---|---|---|---|
| `200% text keeps the chat and privacy screens readable without sideways scrolling` | pull_request and push, overflow 5 px | On the runner, the `"Segoe UI", system-ui` stack falls back to DejaVu Sans, which is wider. At 390 px with 200% text, the one-word brand link (a flex item with `min-width:auto`) plus the 44 px privacy button no longer fit. The button ended at x=395 on `/#/settings`. Windows and the stock Playwright image resolve narrower fonts, so it passed locally | `me2we.css`: header `gap: 8px`; the brand link may shrink (`min-width: 0`) and the brand word may wrap (`overflow-wrap: anywhere`) only when it cannot fit. No change at ordinary sizes | Reproduced with Chromium from `mcr.microsoft.com/playwright:v1.64.1-noble` plus `fonts-dejavu-core` (run-server, loopback exposed): `Received: 5`. A probe listed `a.icon-button < header.page-app-header` at right=395. After the fix: overflow 0, test passes |
| `sending, accepted and final states are truthful and the orb runs only after acceptance` | push only | Test-fixture defect: the `aiRun` synthetic transcript always returned `messages: []`, so the reconciliation read after `final` wiped the reply, which no real server does. The assertion passed only when its first poll landed inside the short window before reconciliation | `aiRun` now stores the accepted self message and, on completion, the reply. The test waits for the run to settle (Stop gone, one transcript read) before asserting the reply, so it checks the stored result rather than a transient frame. No assertion removed or timeout raised | Reordered test with the old fixture: deterministic RED 3/3, `element(s) not found`, the CI error. With the faithful fixture: GREEN 10/10 |

Re-verification after these changes. Evidence is in `canonical-back-fix-20261027/` and its `linux-probe/`; the container was removed afterwards.

| Check | Result |
|---|---|
| Full configured E2E, Windows Chromium, owned Vite 5191 | PASS, 185/185, 0 skipped, 0 flaky (`e2e-full-2.txt`, `results-full-2.json`) |
| Full configured E2E, Linux Chromium + DejaVu (container) | PASS, 185/185 (`linux-probe/e2e-full-linux.txt`) |
| `ux-redesign.spec.ts` alone | PASS, 60/60 |
| `npm.cmd run typecheck` / `npm.cmd test` / `npm.cmd run build` | PASS / 73/73 / PASS (`typecheck-2.txt`, `unit-2.txt`, `build-2.txt`) |
