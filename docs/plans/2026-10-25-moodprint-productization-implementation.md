# MoodPrint Productization — Implementation Plan

> **For agentic workers:** execute task by task with `superpowers:executing-plans` or `superpowers:subagent-driven-development` if the Superpowers plugin is installed; otherwise use the project-local skills `/test-first-engineering` (per task), `/feature-delivery`, `/root-cause-debugging` (on failures) and `/evidence-gated-completion` (before marking a task done). Steps use checkboxes (`- [ ]`) for tracking; tick them in this file as you go and record evidence in `docs/productization/evidence/`.

**Goal:** turn MoodPrint into a real multi-user product for ~50 users: remove the prototype, stabilize human connections, ship explainable matching v2, three server-authoritative shared activities, staff moderation and release qualification.

**Architecture:** extend the existing FastAPI modular monolith (single worker) and React/Vite SPA. Activities are a new backend module reusing pair locks, idempotency receipts, consent-version gates and the per-connection SSE watermark; matching v2 is a deterministic taxonomy scorer behind a version flag. Four expand-only Alembic migrations (0011–0014).

**Tech stack:** Python 3.12.13, FastAPI, Pydantic 2, SQLAlchemy async + psycopg 3, Alembic, uv · React 19, Vite 7, TypeScript 5.9, react-router 7, Vitest, Playwright · Supabase PostgreSQL 17 (+pgvector 0.8.2) · OpenAI Agents SDK (unchanged).

**Spec:** [design](2026-10-25-moodprint-productization-design.md) and [docs/productization/](../productization/README.md) (requirements [03](../productization/03-product-requirements.md), architecture [04](../productization/04-target-architecture.md), matching [05](../productization/05-matching-design.md), activities [06](../productization/06-shared-activities-design.md), contracts [07](../productization/07-database-and-api-contracts.md), UX [08](../productization/08-frontend-ux-plan.md), security [09](../productization/09-security-privacy-operations.md), tests [10](../productization/10-testing-evaluation-strategy.md), migrations [11](../productization/11-migration-and-rollback.md)).

## Global Constraints

- Preserve the stack; no new services, brokers, realtime vendors or dependencies unless a task says so (none do).
- Production must never show fake users, fabricate replies, simulate success or fall back to demo data.
- Never use moods, notes, private items, AI conversations, memories or activity answers as matching inputs.
- Never display numeric compatibility or claim psychological compatibility.
- Every write endpoint: `require_actor` (CSRF + Origin), `Idempotency-Key` receipt, `expectedVersion` CAS where state can change, canonical lock order users → pair → connection → activity session.
- Every new table: RLS + ACL block copied from `backend/alembic/versions/0006_ai_usage.py`; migrations expand-only, `downgrade()` raises; use `'…' || quote_ident(x)`, never `format('%I')`.
- Tests run only against local disposable `*_test` databases; `backend/.env` points at the hosted project and must never drive tests or Alembic.
- No hosted SQL, AWS changes, deployments, billable live AI runs or hosted fixture runs without explicit user approval in that session.
- Do not edit files under `frontend/` while a full-stack browser run is in progress (Vite HMR resets pages).
- Restore `docs/plans/validation-artifacts/visual/*` if the full-stack harness rewrites them.
- Keep Vietnamese UI copy consistent with existing screens; keep code style of surrounding files (dense, typed, small helpers).

## Review Focus (likely real-world failures → owning test)

| Failure condition | Test (task) |
|---|---|
| Both users invite each other to an activity at the same moment | T-ACT-02 (D-03) |
| Peer's unrevealed Icebreaker answer or quiz `correctIndex` appears in any JSON response | T-ICE-01 (E-02), T-QUIZ-01 (F-02) |
| User blocks/ends/withdraws MATCH while an activity is mid-round in the peer's open tab | T-ACT-04 (D-05), T-ACT-03 (J-01) |
| Republishing a profile with a different goal silently closes a friendship | T-CONN-02 (B-02) |
| Phone sleeps during Focus; countdown on return is wrong | T-FOCUS-01 (G-01), T-FOCUS-02 (J-01) |
| Retry of a response submit after a network timeout creates a 409 instead of the same view | T-ICE-01 (E-02) |
| Sweeper and a user action touch the same session (expiry vs accept) | T-ACT-02 (D-06) |
| A v1-shaped profile meets a v2 profile in ranking | T-MATCH-03 (C-03) |
| Popular user floods with requests; the same people always appear first | T-MATCH-04 (C-04) |
| Unread count goes negative or backwards with out-of-order read calls | T-CONN-04 (B-05) |
| Suspended user keeps an open SSE stream | T-MOD-02 (I-03) |
| AI quota day boundary in Asia/Bangkok vs UTC | T-AIQ-01 (I-05) |

## Common commands

Run in Git Bash from the repository root unless stated (PowerShell equivalents: `npm.cmd`, `$env:VAR=`).

- **VC-DB** (prepare/refresh a disposable DB; `<name>` must end `_test`):
  ```bash
  PW=$(docker exec moodprint-ai-memory-pg printenv POSTGRES_PASSWORD)
  docker exec -e PGPASSWORD="$PW" moodprint-ai-memory-pg dropdb -U postgres --if-exists <name>
  docker exec -e PGPASSWORD="$PW" moodprint-ai-memory-pg createdb -U postgres <name>
  export TEST_DATABASE_URL="postgresql+psycopg://postgres:${PW}@127.0.0.1:16432/<name>"
  ```
- **VC-BE**: `cd backend && uv run --locked ruff check app tests evals alembic && uv run --locked mypy app && uv run --locked pytest -q` → ruff "All checks passed!", mypy "Success", pytest "N passed" with 0 failed/0 errors (N ≥ previous count).
- **VC-BE-T `<file>`**: `cd backend && uv run --locked pytest -q tests/<file>` → stated pass count.
- **VC-MIG**: VC-DB with `prodmig_test`, then `cd backend && DATABASE_URL='' DATABASE_MIGRATION_URL="postgresql+psycopg://postgres:${PW}@127.0.0.1:16432/prodmig_test" uv run alembic upgrade head && DATABASE_URL='' DATABASE_MIGRATION_URL=… uv run alembic check` → last line "No new upgrade operations detected."
- **VC-SQL `<from>:<to> <NNNN>`** (review SQL; must byte-match what `scripts/apply_supabase_review.py` regenerates, so use exactly this environment):
  ```bash
  mkdir -p docs/productization/migrations
  cd backend && DATABASE_URL=postgresql+psycopg://localhost/moodprint_review_test DATABASE_MIGRATION_URL= AI_ENABLED=false STT_ENABLED=false \
    uv run python -m alembic upgrade <from>:<to> --sql > ../docs/productization/migrations/<NNNN>-review.sql
  grep -c "%%" ../docs/productization/migrations/<NNNN>-review.sql   # expected 0
  grep -ciE "\b(DROP|TRUNCATE)\b" ../docs/productization/migrations/<NNNN>-review.sql   # expected 0
  ```
- **VC-CONTRACT**: `cd backend && uv run --locked python ../scripts/export_openapi.py && cd ../frontend && npm run contracts:generate && npm run typecheck` → exit 0; commit both `backend/openapi.json` and `frontend/src/api/generated/schema.d.ts`.
- **VC-FE**: `cd frontend && npm run typecheck && npm test && npm run build && npm run test:e2e` → all exit 0.
- **VC-FS**: VC-DB with `prod_e2e_test`; `cd backend && uv run --locked python ../scripts/test_fullstack.py` → "passed" for every spec; then `git status --short docs/plans/validation-artifacts/visual` → restore with `git checkout -- docs/plans/validation-artifacts/visual` if changed.

## Dependency graph

```mermaid
flowchart TD
  A01[A-01 baseline] --> A02[A-02 remove prototype] --> A03[A-03 prune UI/CSS]
  A02 --> A04[A-04 rename package]
  A01 --> A05[A-05 retire outbox]
  A01 --> B01[B-01 pair alias] --> B03[B-03 request card]
  A01 --> B02[B-02 durable connections]
  A01 --> B04[B-04 migration 0011] --> B05[B-05 unread + summary]
  B01 --> B05
  B04 --> B06[B-06 last_seen]
  A01 --> C01[C-01 taxonomy v2] --> C02[C-02 migration 0012 + profile v2]
  B04 --> C02
  C01 --> C03[C-03 scorer v2]
  C02 --> C04[C-04 retrieval/ranking/flag]
  C03 --> C04
  B06 --> C04
  B02 --> C04
  C04 --> C05[C-05 explanations + DTO]
  C03 --> C06[C-06 offline eval]
  C02 --> C07[C-07 editor + cards UI]
  C05 --> C07
  B03 --> C07
  C04 --> C08[C-08 beta metrics]
  C02 --> D01[D-01 migration 0013 + models]
  B02 --> D01
  A01 --> D02[D-02 machine + definitions]
  D01 --> D03[D-03 lifecycle API]
  D02 --> D03
  D03 --> D04[D-04 SSE activity_changed]
  D03 --> D05[D-05 lifecycle hooks/export/retention]
  D03 --> D06[D-06 sweeper]
  D04 --> D07[D-07 FE activity infra]
  A03 --> D07
  D02 --> E01[E-01 icebreaker bank] --> E02[E-02 icebreaker API]
  D03 --> E02 --> E03[E-03 icebreaker UI]
  D07 --> E03
  D02 --> F01[F-01 quiz bank] --> F02[F-02 quiz API]
  D03 --> F02 --> F03[F-03 quiz UI]
  D07 --> F03
  D02 --> G01[G-01 focus timer model] --> G02[G-02 focus API + transitions]
  D03 --> G02
  D06 --> G02 --> G03[G-03 focus UI]
  D07 --> G03
  B05 --> H01[H-01 nav badges + Discovery IA]
  C07 --> H01
  E03 --> H02[H-02 chat dock layout]
  F03 --> H02
  G03 --> H02
  H01 --> H03[H-03 states sweep]
  H02 --> H03 --> H04[H-04 responsive + a11y evidence]
  D01 --> I01[I-01 migration 0014 + moderation API]
  I01 --> I02[I-02 admin screen + runbook]
  A03 --> I02
  I01 --> I03[I-03 enforcement]
  C04 --> I03
  D05 --> I03
  E02 --> I04[I-04 activity evidence + privacy]
  F02 --> I04
  I01 --> I04
  A01 --> I05[I-05 AI quota/budget]
  A02 --> I06[I-06 PII advisory]
  A01 --> I07[I-07 ops runbooks/alarms]
  A01 --> I08[I-08 privacy notice draft]
  H04 --> J01[J-01 full-stack journeys]
  I03 --> J01
  I04 --> J01
  J01 --> J02[J-02 50-user load]
  I01 --> J03[J-03 hosted migration review]
  J02 --> J04[J-04 staging deploy]
  J03 --> J04
  J04 --> J05[J-05 release readiness]
  C06 --> J05
  I08 --> J05
```

## Progress checklist

- [ ] A-01 · [ ] A-02 · [ ] A-03 · [ ] A-04 · [ ] A-05
- [ ] B-01 · [ ] B-02 · [ ] B-03 · [ ] B-04 · [ ] B-05 · [ ] B-06
- [ ] C-01 · [ ] C-02 · [ ] C-03 · [ ] C-04 · [ ] C-05 · [ ] C-06 · [ ] C-07 · [ ] C-08
- [ ] D-01 · [ ] D-02 · [ ] D-03 · [ ] D-04 · [ ] D-05 · [ ] D-06 · [ ] D-07
- [ ] E-01 · [ ] E-02 · [ ] E-03
- [ ] F-01 · [ ] F-02 · [ ] F-03
- [ ] G-01 · [ ] G-02 · [ ] G-03
- [ ] H-01 · [ ] H-02 · [ ] H-03 · [ ] H-04
- [ ] I-01 · [ ] I-02 · [ ] I-03 · [ ] I-04 · [ ] I-05 · [ ] I-06 · [ ] I-07 · [ ] I-08
- [ ] J-01 · [ ] J-02 · [ ] J-03 (approval) · [ ] J-04 (approval) · [ ] J-05

**MVP** = all tasks above. **Post-MVP** (not in this plan): English practice, semantic profile embeddings, push/email notifications, global per-user SSE, multi-worker, unblock/appeals UI, outbox table drop, removal of the v1 scorer.

Relative complexity: S ≤ ½ day · M ≈ 1 day · L ≈ 2–3 days (single engineer + agent).

---

## Phase A — Production baseline and prototype cleanup

### A-01 — Baseline snapshot and working branch (S)

- **Description:** record the starting evidence and create the implementation branch.
- **Depends:** —
- **Files:** create `docs/productization/evidence/baseline.md`.
- **Migration / API:** none.
- **Tests first:** none (measurement only).
- **Steps:**
  - [ ] `git status --short` → only user changes (e.g. ` M .gitignore`); do not touch them.
  - [ ] `git switch -c feat/productization` from `main` at or after `5689dd9`.
  - [ ] VC-DB (`prod_test`) → VC-BE; VC-FE; optionally VC-FS.
  - [ ] Write counts, durations and any pre-existing failures to `baseline.md`.
- **Acceptance:** baseline file lists exact commands and counts.
- **Verify / expected:** pytest "278 passed" (or the current count); vitest "89 passed"; mocked E2E 34 passed; full-stack 13 passed (if run).
- **Rollback:** delete branch.

### A-02 — Remove the legacy prototype (M)

- **Description:** delete prototype sources, harness and tests per [02](../productization/02-prototype-removal-inventory.md); add guard tests.
- **Depends:** A-01
- **Files:**
  - Delete: `frontend/src/App.tsx`, `frontend/src/pages/` (6 files), `frontend/src/state/` (2), `frontend/src/mocks/` (3), `frontend/src/domain/` (5 incl. `domain.test.ts`), `frontend/src/companions/{Cards.tsx,Companions.tsx,scenarios.ts,companions.test.ts}`, `frontend/tests/harness/` (2), `frontend/playwright.legacy.config.ts`, `frontend/tests/e2e/journeys.spec.ts`, `frontend/tests/{visual-review.mjs,screenshots.mjs,production-smoke.mjs}`, `frontend/evidence/legacy-results.json`, `frontend/evidence/legacy/`.
  - Modify: `frontend/package.json` (remove `test:e2e:legacy`).
  - Create: `frontend/src/productionGuard.test.ts`, `backend/tests/test_production_imports.py`.
- **Tests first:**
  - `productionGuard.test.ts`: walk `src/` (node `fs`), fail if any file matches `/from\s+["'][^"']*(\/mocks\/|\/state\/|\/domain\/|\/pages\/|companions\/(Cards|Companions|scenarios))/` or if `src/App.tsx` exists. Run → **fails** (prototype present).
  - `test_production_imports.py`: AST-scan `backend/app/**/*.py`; assert no import starting with `tests` or `evals`. Run → passes (guard only).
- **Steps:**
  - [ ] Write both tests; `npm test` shows the guard failing.
  - [ ] Delete the files; `npm test` → 12 existing + guard pass.
  - [ ] `npm run typecheck && npm run build`; `grep -R "Mô phỏng\|bản mẫu\|fixture=" frontend/dist | wc -l` → 0.
  - [ ] `npm run test:e2e` → all pass (34).
  - [ ] `git grep -n "test:e2e:legacy\|playwright.legacy\|legacy-main" -- . ':!docs'` → no output.
- **Acceptance:** T-CLEAN-01, T-CLEAN-02; deletion checklist in [02 §5](../productization/02-prototype-removal-inventory.md#5-deletion-safety-checklist-a-02-must-satisfy).
- **Verify:** VC-FE → exit 0; VC-BE-T `test_production_imports.py` → 1 passed.
- **Rollback:** `git revert <commit>`.

### A-03 — Prune legacy-only UI exports and CSS (S)

- **Depends:** A-02
- **Files:** modify `frontend/src/components/UI.tsx` (remove `Go`, `Badge`, `Intro`, `Tabs`, `useTab`, `Avatar`, `Garden` and now-unused imports), `frontend/src/styles/App.module.css`, `frontend/src/styles/me2we.css`.
- **Tests first:** extend `productionGuard.test.ts`: every exported name of `components/UI.tsx` is imported somewhere under `src/features` (fails before pruning).
- **Steps:**
  - [ ] Remove the exports; `npm run typecheck`.
  - [ ] For each class in `App.module.css`, `grep -R "cx\.<name>\b\|cx\[\"<name>\"\]" frontend/src` → delete classes with 0 hits. For `me2we.css`, delete selectors whose class names do not appear in `frontend/src/features` or `index.html`.
  - [ ] VC-FE; VC-FS (screens unchanged; compare 390/1440 screenshots of Assistants, Mood, Connect, Messages, Chat with the previous run by eye).
- **Acceptance:** guard passes; no visual regression on production screens; axe still 0 violations.
- **Verify:** VC-FE exit 0; VC-FS all pass.
- **Rollback:** revert commit.

### A-04 — Rename package and update docs (S)

- **Depends:** A-02
- **Files:** `frontend/package.json` (`"name": "moodprint-web"`), `frontend/package-lock.json` (the two top-level `name` fields only), `frontend/README.md`, root `README.md` (mention new docs entry `docs/productization/README.md`).
- **Tests first:** T-CLEAN-03 as a guard assertion in `productionGuard.test.ts` reading `package.json`.
- **Steps:** [ ] edit names · [ ] `npm ci` succeeds without lockfile changes beyond the names (`git diff --stat frontend/package-lock.json` shows 2 lines) · [ ] `npm audit --audit-level=low` → 0 · [ ] VC-FE.
- **Acceptance:** T-CLEAN-03; no dependency version changes.
- **Rollback:** revert.

### A-05 — Retire the write-only outbox (S)

- **Depends:** A-01
- **Files:** modify `backend/app/modules/social/routes.py` (remove `Outbox(...)` inserts in `publish`, `withdraw`, `send_message`, `block_peer`), `backend/app/modules/social/service.py` (`open_mutual_room`), `backend/app/modules/consent/routes.py` (consent change), `backend/app/jobs/retention.py` (purge `Outbox` rows ≤ 1000 per minute, oldest first), `backend/app/infrastructure/database/models.py` (docstring: retired, kept until contract migration). Create `backend/tests/test_outbox_retired.py`.
- **Tests first:** (1) after publish + message + block + consent toggle, `select count(*) from moodprint.outbox` == 0 → fails today; (2) seed 3 outbox rows, call `purge_expired(app)`, count == 0.
- **Steps:** [ ] tests fail · [ ] remove writes, add purge · [ ] VC-BE-T `test_outbox_retired.py` → 2 passed · [ ] VC-BE.
- **Acceptance:** no `Outbox(` constructor left under `backend/app` except the model; `git grep -n "Outbox(" backend/app` → only `models.py`.
- **Rollback:** revert (writes resume; harmless).

## Phase B — Real-user experience stabilization

### B-01 — One pseudonymous alias per pair (S)

- **Depends:** A-01
- **Files:** `backend/app/modules/social/service.py` (add `pair_alias`, use in `connection_view`), `backend/app/modules/social/routes.py` (`candidates` uses `pair_alias`), `backend/app/modules/users/export.py` (alias map). Create `backend/tests/test_pair_alias.py`.
- **Interfaces:** produces `def pair_alias(a: UUID, b: UUID) -> tuple[str, str]` returning `("Bạn đồng hành " + seed[:6], seed)` where `seed = digest(":".join(sorted((str(a), str(b)))))[:8]` (same as today's candidate formula). `connection_view(room)` computes it from `room.low_user_id, room.high_user_id`.
- **Tests first:** open a room (helpers from `test_social.py`), assert candidate alias (captured before request) == `GET /connections` alias == export `social.connections[].peer` for both users → fails today.
- **Steps:** [ ] test fails · [ ] implement · [ ] VC-BE-T `test_pair_alias.py` · [ ] VC-BE.
- **Acceptance:** T-CONN-03.
- **Rollback:** revert (aliases change back; cosmetic).

### B-02 — Connections survive profile edits (DR-03) (M)

- **Depends:** A-01
- **Description:** room/request validity depends on consent versions, blocks and account state — not on profile versions. Publish/withdraw no longer call `invalidate_user_social`.
- **Files:** `backend/app/modules/social/service.py`, `backend/app/modules/social/routes.py`, `backend/app/modules/social/retrieval.py`, `frontend/src/features/real/Social.tsx` (publish dialog info line "Các kết nối hiện có vẫn được giữ"), `frontend/src/features/real/RealApp.tsx` (no copy change for MATCH). Create `backend/tests/social_helpers.py` (move `key`, `consent`, `publish`, `published_pair`, `open_room` from `test_social.py`; import them back there) and `backend/tests/test_connection_durability.py`. Rename `test_republish_and_match_reenable_never_resurrect_room` → `test_match_reenable_never_resurrects_room` (body unchanged).
- **Interfaces (produce):**
  - `async def room_gate(db, a: User, b: User) -> dict[str, dict[str, int]]` — `deny()` if blocked or either fails `match_consent`; returns `{str(id): {"consent": version}}` for both.
  - `def consent_view(snapshots: dict) -> dict[str, int]` → `{uid: snapshots[uid]["consent"]}`.
  - `live_room` uses `room_gate` and compares `consent_view(room.snapshots) == consent_view(gate)`; `interaction()` compares consent views; `list_connections` uses `room_gate`; `decide()` uses `room_gate` for decline/cancel and `base_eligibility` (profiles still required) for accept, comparing consent views.
  - `publish` and `withdraw` drop the `invalidate_user_social` call. MATCH withdrawal (`consent/routes.py`) and deletion keep it.
  - **Every** remaining full-snapshot comparison becomes a consent-view comparison, otherwise an already-connected peer who republished reappears as a candidate: `retrieval.py` (`pending_row.snapshots == snapshots`, `room.snapshots == snapshots`, today lines 109/112), the `candidates` route recheck (`routes.py` 283/287), `decide()` replay and validation (`routes.py` 425/432) and `list_connections` (`routes.py` 489). Simplest correct rule for discovery: any **open** room or **unexpired pending** request for the pair excludes the peer regardless of snapshots. `check_reference` keeps comparing profile versions (candidate cards must be fresh).
  - Paths already covered through `live_room`: `get_connection`, `send_message`, `get_messages`, SSE `events`/`event_stream`, moderation `request_reveal`/`list_reveals`/`grant`/`revealed_value` — no separate change needed; add one regression test that a reveal grant still works after a republish.
- **Tests first (`test_connection_durability.py`):**
  1. open room → A republishes with different interests → both can GET/POST messages; SSE stream stays open (no `access_revoked` within 3 s).
  2. open room → A withdraws profile → messaging still works; A is absent from B's candidates.
  3. pending request → sender republishes compatible profile → recipient accepts → 200, room opens.
  4. pending request → sender withdraws profile → accept → 409 `REQUEST_CHANGED`; decline → 200.
  5. MATCH off still closes the room (existing behavior, regression).
  6. After A republishes while the room is open, A is **not** in B's candidates and B is not in A's (discovery exclusion).
  7. Reveal request/grant still works after a republish.
  Run → 1–3, 6, 7 fail today.
- **Steps:** [ ] move helpers, tests green as before · [ ] write new tests (fail) · [ ] implement · [ ] VC-BE-T `test_connection_durability.py` → 7 passed · [ ] VC-BE · [ ] VC-FS.
- **Acceptance:** T-CONN-02; all existing social/matching tests pass unchanged except the rename.
- **Rollback:** revert; rooms opened meanwhile stay open (acceptable, [11 §5](../productization/11-migration-and-rollback.md#5-rollback-strategy)).

### B-03 — Sender/recipient card on pending requests (M)

- **Depends:** B-01
- **Files:** `backend/app/modules/social/schemas.py` (`PeerCardDTO`, `RequestView.peer`), `backend/app/modules/social/routes.py` (`list_requests`), `backend/app/modules/social/service.py` (`peer_card(db, user, peer) -> PeerCardDTO | None`), `frontend/src/features/real/Social.tsx` (render card in request items), `frontend/tests/e2e/social.spec.ts` (mocked state). Create `backend/tests/test_request_cards.py`.
- **API contract:** `PeerCardDTO {alias, avatarSeed, profile: PublicProfile, reasons: list[str] ≤3, matchLabel: "many"|"some"}`; `RequestView.peer: PeerCardDTO | null` — present only for `pending` rows when `base_eligibility` passes; `matchLabel` from current scorer (`v1`: score ≥ 60 → many).
- **Tests first:** incoming and outgoing pending rows include `peer` with the counterpart's published tags and alias equal to `pair_alias`; after block → `peer` null (row invalidated); C (third user) cannot see either request.
- **Steps:** [ ] backend tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] UI: card above Accept/Decline · [ ] mocked E2E case "incoming request shows sender card" · [ ] VC-BE, VC-FE.
- **Acceptance:** T-CONN-01.
- **Rollback:** revert (field optional).

### B-04 — Migration `0011_social_stabilization` and tolerant readiness (M)

- **Depends:** A-01
- **Files:** create `backend/alembic/versions/0011_social_stabilization.py`; modify `backend/app/infrastructure/database/models.py` (`User.last_seen_at`), `backend/app/modules/social/models.py` (`ConnectionRead`, indexes on `Block.blocked_id`, `CandidateReference.peer_id`, `ConnectionRequest(recipient_id,status)`), create `backend/app/core/revisions.py` (`READY_REVISIONS: tuple[str, ...] = ("0010_account_deletion", "0011_social_stabilization")` — the only place heads are listed; see the release note below), `backend/app/main.py` (import it; `if revision not in READY_REVISIONS`), `scripts/inspect_database.py` (already puts `backend/` on `sys.path`; `from app.core.revisions import READY_REVISIONS` and use `entry["revisions"][0] in READY_REVISIONS` for `head_matches`), `scripts/apply_supabase_review.py` (`"0011": UpgradePlan(review=ROOT/"docs/productization/migrations/0011-review.sql", report=…/0011-execution.json, from "0010_account_deletion", to "0011_social_stabilization", tables=("connection_reads",))`), `deploy/README.md` (readiness note).
- **Migration:** DDL in [07 §2.1](../productization/07-database-and-api-contracts.md#21-0011_social_stabilization) + ACL block for `connection_reads`.
- **Tests first:** `tests/test_readiness.py`: readiness returns 200 when `alembic_version` is any value in `READY_REVISIONS`, 503 otherwise (create the `moodprint.alembic_version` table in the test DB and insert values).
- **Steps:** [ ] test fails · [ ] models + migration + constants · [ ] VC-MIG → "No new upgrade operations detected." · [ ] generate offline SQL with **VC-SQL** `0010_account_deletion:0011_social_stabilization 0011` · [ ] VC-BE (includes `test_reviewed_upgrade_sql_executes_verbatim`, which now executes 0011 offline SQL and checks `backend_access` on `connection_reads`).
- **Acceptance:** T-MIG-01 (local part).
- **Release note:** commit `revisions.py` + the probe change first (as its own commit with `READY_REVISIONS = ("0010_account_deletion", "0011_social_stabilization")`) so it can ship as release R0.5 before 0011 is applied ([11 §3](../productization/11-migration-and-rollback.md#3-readiness-check-change-task-b-04)); the second commit adds the migration and keeps both heads; C-02 later replaces the tuple with `("0011_social_stabilization", "0012_matching_v2")`.
- **Rollback:** app revert; schema additive (no hosted apply in this task — hosted happens in J-03).

### B-05 — Unread counts, last message preview, social summary (M)

- **Depends:** B-04, B-01
- **Files:** `backend/app/modules/social/routes.py` (`POST /connections/{id}/read`, enrich `list_connections`), `backend/app/modules/social/schemas.py` (`ReadInput {seq: str ^\d{1,19}$}`, `ReadView {lastReadSeq}`, `ConnectionView` + `unreadCount`, `lastMessageAt`, `lastMessagePreview`, `SocialSummaryView`), new `backend/app/modules/social/summary.py` (`GET /social/summary`, router included in `main.py`), `frontend/src/features/real/Social.tsx` (`HumanMessages` rows; `HumanChat` posts read marker when newest message visible, debounced 1 s), `frontend/src/features/real/RealApp.tsx` (`Navigation` badges via new `useSocialSummary`). Create `backend/tests/test_unread.py`.
- **API contract:** see [07 §3.1](../productization/07-database-and-api-contracts.md#31-social-stabilization-b). Read upsert: `INSERT … ON CONFLICT (connection_id,user_id) DO UPDATE SET last_read_seq = GREATEST(connection_reads.last_read_seq, EXCLUDED.last_read_seq)`; seq clamped to `room.next_seq`; requires `live_room(lock=False)`. Unread = peer messages with `seq > last_read_seq` within 90 days, computed in one grouped query for all listed rooms. `lastMessagePreview` = first 80 chars of the newest message text, prefixed per sender in the UI.
- **Tests first:** peer sends 3 → `unreadCount` 3 → read seq 2 → 1 → read seq 1 (older) → still 1 → read 3 → 0; summary counts pending incoming requests and unread connections; MATCH off → summary zeros (200); C cannot mark A/B room read (404/403).
- **Steps:** [ ] tests fail · [ ] backend · [ ] VC-CONTRACT · [ ] UI + mocked E2E (badge renders with count, `aria-label`) · [ ] VC-BE, VC-FE.
- **Acceptance:** T-CONN-04.
- **Rollback:** revert; table stays unused.

### B-06 — Record `last_seen_at` (S)

- **Depends:** B-04
- **Files:** `backend/app/core/security.py` (in `require_actor`, when the sliding-expiry update runs, also `update(User).values(last_seen_at=now())`), `backend/tests/test_auth_flows.py` (new case).
- **Tests first:** first authenticated request sets `last_seen_at`; a second request within 15 min does not change it (no extra write).
- **Steps:** [ ] test fails · [ ] implement · [ ] VC-BE.
- **Acceptance:** column populated for active users; no additional queries on the hot path beyond the existing 15-minute write.
- **Rollback:** revert.

## Phase C — Matching improvements

### C-01 — Taxonomy v2 as single source of truth (M)

- **Depends:** A-01
- **Files:** create `backend/app/modules/profiles/taxonomy_v2.json` (facets, labels, categories, similarity, goal/style matrices per [05 §3](../productization/05-matching-design.md#3-taxonomy-v2-single-source-of-truth)); modify `backend/app/modules/profiles/taxonomy.py` (load + validate JSON at import; export `TAXONOMY`, `INTERESTS`, `VALUES`, `STYLES`, `GOALS`, `LANGUAGES`, `ACTIVITIES`, `AVAILABILITY`, `interest_similarity(a,b)`, `goal_compat(a,b)`, `style_compat(a,b)`), `backend/app/modules/social/schemas.py` (validators import from `profiles.taxonomy`, not `matching.scoring`), `backend/app/modules/matching/scoring.py` (v1 keeps its **own frozen v1 dicts** for oracle parity; rename `SCORING_VERSION = "rules-v1"`), `backend/app/modules/social/schemas.py` (`scoring_version: Literal["rules-v1","rules-v2"]`). Create `backend/tests/test_taxonomy_v2.py`.
- **Tests first:** JSON loads; every v1 key present in v2; similarity symmetric, 1.0 on diagonal, values in [0,1]; every interest in exactly one category; goal/style matrices symmetric and complete; `GET /taxonomy` returns version `v2` with new facets; existing `test_oracles.py` unchanged and passing.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** `git grep -n "from app.modules.matching.scoring import _" backend/app` → no output.
- **Rollback:** revert.

### C-02 — Migration `0012_matching_v2` and profile v2 schema (M)

- **Depends:** C-01, B-04
- **Files:** create `backend/alembic/versions/0012_matching_v2.py`; modify `backend/app/modules/social/models.py` (`PublishedProfile.taxonomy_version`, `CandidateReference.scoring_version`, `rank`, new `MatchingStatsDaily`), `backend/app/modules/social/schemas.py` (`PublicProfile.activities`, `availability`, `strict_goal`; min/max rules per facet), `backend/app/modules/social/service.py` (`validate_publishable` → v2 rules; `public_payload` includes new fields), `backend/app/modules/social/routes.py` (`publish` sets `taxonomy_version="v2"`), `backend/app/core/config.py` (`matching_scorer: Literal["v1","v2","shadow"] = "v1"`), `backend/.env.example`, `deploy/runtime.env.example`, `backend/app/core/revisions.py` (`READY_REVISIONS = ("0011_social_stabilization", "0012_matching_v2")`), `scripts/apply_supabase_review.py` (`"0012"` plan, `tables=("matching_stats_daily",)`). Create `backend/tests/test_profile_v2.py`.
- **Migration:** [07 §2.2](../productization/07-database-and-api-contracts.md#22-0012_matching_v2) + ACL block for `matching_stats_daily`.
- **Tests first:** publish v2 profile (activities, availability, strictGoal) → stored with `taxonomy_version='v2'`; v1-shaped draft still publishes; too many interests (11) → 422; unknown activity → 422; v1 scorer ignores new fields (score unchanged for same core tags).
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-MIG · [ ] VC-SQL `0011_social_stabilization:0012_matching_v2 0012` · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-MATCH-02; T-MIG-01 (local).
- **Rollback:** app revert; columns defaulted.

### C-03 — Scorer `rules-v2` (pure) (M)

- **Depends:** C-01
- **Files:** create `backend/app/modules/matching/scoring_v2.py`, `backend/tests/test_scoring_v2.py`.
- **Interfaces (produce):**
  ```python
  SCORING_VERSION = "rules-v2"
  @dataclass(frozen=True)
  class Breakdown: score: float; components: dict[str, float]; coverage: float; shared: dict[str, list[str]]
  def score(a: Mapping[str, Any], b: Mapping[str, Any]) -> Breakdown   # a, b = published payloads
  def eligible(b: Breakdown) -> bool                                    # score ≥ 0.30 and any exact shared interest/value/activity
  def label(b: Breakdown) -> Literal["many", "some"]                    # ≥ 0.60 → many
  def goal_allowed(a, b) -> bool                                        # strictGoal on either side ⇒ equal goals
  ```
  Formula exactly as [05 §4](../productization/05-matching-design.md#4-explainable-scoring-formula).
- **Tests first:** worked example ([05 §4.2](../productization/05-matching-design.md#42-worked-example)) → 0.690 ± 0.001; symmetry over 1,000 seeded random pairs; bounds; missing activities/availability renormalize (coverage 0.75–1.0); identical full profiles → 1.0; no shared exact item → `eligible` False even if score ≥ 0.30; `shared` contains only items in both; deterministic.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE-T `test_scoring_v2.py` → all pass.
- **Acceptance:** T-MATCH-03.
- **Rollback:** unused module until C-04 flag.

### C-04 — Retrieval v2, ranking, fairness and scorer flag (L)

- **Depends:** C-02, C-03, B-06, B-02
- **Files:** rewrite `backend/app/modules/social/retrieval.py` (`eligible_peers(db, user, own, own_consent, now) -> list[PeerRow]` with the SQL in [05 §9](../productization/05-matching-design.md#9-sql-retrieval-design); `ranked_candidates(...)` dispatching by `settings.matching_scorer`); create `backend/app/modules/matching/ranking.py` (`rank(viewer_id, rows, breakdowns, local_date) -> list[UUID]`: cold-start +0.03 for 7 days, load penalty `0.05·max(0, pending−2)`, MMR λ 0.85 by interest component, daily tie-break hash); modify `backend/app/modules/social/service.py` (`base_eligibility`: goal rule → `scoring_v2.goal_allowed` when scorer ≠ v1; language overlap unchanged), `backend/app/modules/social/routes.py` (`candidates`: record `scoring_version`, `rank` on `CandidateReference`; shadow logging; shortlist stays 10). Create `backend/tests/test_matching_retrieval_v2.py`, `backend/tests/test_matching_privacy.py`, `backend/tests/test_ranking.py`.
- **Interfaces:** consumes `scoring_v2`, `taxonomy`, `users.last_seen_at`; produces `ranked_candidates` (same signature as today) and `CandidateReference.scoring_version`.
- **Tests first:**
  - Parametrized exclusion rules (T-MATCH-01), including inactive 31 days (`last_seen_at`), profile 181 days, NULL `last_seen_at` treated as active until `LAST_SEEN_ENFORCED_FROM`.
  - Soft goals: `friendship` vs `study-buddy` both visible under v2; strictGoal on either side hides.
  - Ranking (T-MATCH-04): same day → same order; next day → different tie order for equal scores; load penalty demotes a peer with 5 pending incoming; cold-start boost; MMR avoids 3 near-identical profiles in top 3 when a diverse alternative exists.
  - Flag (T-MATCH-05): v1 returns the same order as today's implementation for fixtures from `test_matching_retrieval.py`; shadow serves v1 and logs `matching_shadow` with no IDs (caplog).
  - Privacy (T-MATCH-06): AST scan of `matching/*.py` and `social/retrieval.py` imports.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE · [ ] run existing `tests/performance/benchmark.py` (if applicable) or time 50 synthetic peers → candidates p95 < 600 ms locally.
- **Acceptance:** T-MATCH-01, -04, -05, -06; existing matching tests pass under `v1`.
- **Rollback:** `MATCHING_SCORER=v1`.

### C-05 — Explanations v2 and candidate DTO (S)

- **Depends:** C-04
- **Files:** create `backend/app/modules/matching/explain.py` (`reasons(breakdown, taxonomy) -> list[str]` ≤3, priority: shared activities ("Cả hai muốn thử {label} cùng nhau"), shared interests ("Cùng thích {label}"), shared values ("Cùng coi trọng {label}"), same style, overlapping availability ("Hay rảnh {label}")); modify `backend/app/modules/social/schemas.py` (`CandidateCardDTO` + `matchLabel`, `sharedActivities`), `backend/app/modules/social/routes.py`, `backend/app/modules/social/service.py` (`peer_card` uses `explain` under v2). Create `backend/tests/test_explain.py`.
- **Tests first:** reasons ⊆ shared items (property over 500 random pairs); ≤3; no numbers/percent signs in any reason; label mapping.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-MATCH-03 (faithfulness).
- **Rollback:** flag v1 (v1 reasons function kept).

### C-06 — Offline matching evaluation (M)

- **Depends:** C-03
- **Files:** create `backend/evals/matching/__init__.py`, `personas_v2.json` (60 synthetic personas), `pair_labels.json` (300 pairs × 3 rater labels), `benchmark.py`, `README.md`; output `backend/evals/matching/report.json`.
- **Tests first:** `backend/tests/test_matching_eval.py` runs the benchmark on a 10-persona fixture and asserts metric keys, value ranges, faithfulness 1.0, symmetry violations 0.
- **Steps:** [ ] write personas/labels (team raters; if raters are unavailable, mark labels `provisional` and **do not** flip the flag) · [ ] implement metrics (NDCG@5, P@5, coverage, Gini, faithfulness, symmetry, timing) · [ ] `cd backend && uv run --locked python -m evals.matching.benchmark --out evals/matching/report.json`.
- **Acceptance:** T-EVAL-01 gate documented in the report; decision to set `MATCHING_SCORER=v2` recorded in `docs/productization/evidence/matching-gate.md`.
- **Verify / expected:** report contains `{"v1": {...}, "v2": {...}, "gate": {"passed": true|false, ...}}`.
- **Rollback:** n/a (offline).

### C-07 — Profile editor v2 and candidate card UI (L)

- **Depends:** C-02, C-05, B-03
- **Files:** create `frontend/src/features/real/social/{ProfileEditor.tsx,TagPicker.tsx,CandidateCard.tsx,RequestCard.tsx}`; modify `frontend/src/features/real/Social.tsx` (use new components; keep exports stable), `frontend/src/features/real/real.css`; tests `frontend/src/features/real/social/profileRules.test.ts` (pure min/max/selection helpers), `frontend/tests/e2e/social.spec.ts`.
- **Tests first:** unit tests for `canAdvance(step, profile)` and counters; mocked E2E: stepper requires 3 interests before continuing; preview shows exactly the chosen labels; candidate card shows label + ≤3 reasons and **no digits followed by %**; request card shows sender card.
- **Steps:** [ ] tests fail · [ ] implement per [08 §4](../productization/08-frontend-ux-plan.md#4-discovery-screens) · [ ] VC-CONTRACT if needed · [ ] VC-FE.
- **Acceptance:** T-MATCH-02 (UI), T-CONN-01 (UI).
- **Rollback:** revert.

### C-08 — Aggregated beta metrics (S)

- **Depends:** C-04
- **Files:** `backend/app/modules/social/routes.py` (increment `matching_stats_daily` on impressions in `candidates`, on request creation, on room open), create `backend/app/modules/matching/stats.py` (`async def bump(db, field, scoring_version, day)`), `scripts/report_beta_metrics.py` (read-only; `--database-url-env DATABASE_URL`; refuses to run against hosted unless `--approved` flag; suppresses cells < 5), `backend/tests/test_matching_stats.py`.
- **Tests first:** counters increment exactly once per action (idempotent replay does not double count); report suppresses small cells.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE.
- **Acceptance:** T-METRIC-01.
- **Rollback:** revert; table unused.

## Phase D — Shared activity infrastructure

### D-01 — Migration `0013_shared_activities` and models (M)

- **Depends:** C-02, B-02
- **Files:** create `backend/alembic/versions/0013_shared_activities.py`, `backend/app/modules/activities/__init__.py`, `backend/app/modules/activities/models.py` (`ActivitySession`, `ActivityParticipant`, `ActivityResponse`); modify `backend/app/modules/social/models.py` (`Connection.activity_seq`), `backend/alembic/env.py` and `backend/tests/conftest.py` (import `app.modules.activities.models`), `backend/app/core/revisions.py` (append `"0013_shared_activities"`, drop `"0011_social_stabilization"`), `scripts/apply_supabase_review.py` (`"0013"` plan, `tables=("activity_sessions","activity_participants","activity_responses")`).
- **Migration:** DDL in [06 §7](../productization/06-shared-activities-design.md#7-database-schema-migration-0013_shared_activities) + ACL block per table; model indexes identical (partial unique on `connection_id` for non-terminal states, partial `deadline_at` index).
- **Tests first:** `backend/tests/test_activity_schema.py`: inserting two non-terminal sessions for one connection violates `uq_activity_open_per_connection`; terminal + non-terminal coexist; response CHECK rejects empty answer.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-MIG · [ ] VC-SQL `0012_matching_v2:0013_shared_activities 0013` · [ ] VC-BE.
- **Acceptance:** T-MIG-01 (local).
- **Rollback:** app revert; tables unused.

### D-02 — Activity definitions and pure state machine (M)

- **Depends:** A-01
- **Files:** create `backend/app/modules/activities/definitions.py`, `backend/app/modules/activities/machine.py`, `backend/tests/test_activity_machine.py`.
- **Interfaces (produce):**
  ```python
  Kind = Literal["icebreaker", "coop_quiz", "focus"]
  @dataclass(frozen=True)
  class Definition: kind: Kind; version: str; rounds: int | None; invite_ttl: timedelta; idle_ttl: timedelta | None
  DEFINITIONS: dict[Kind, Definition]
  @dataclass
  class SessionState: id; kind; state; round; phase; inviter_id; invitee_id; content; timer; score; version;
                      participants: dict[UUID, ParticipantState]; responses: dict[tuple[UUID, int], ResponseState]
  @dataclass(frozen=True)
  class Command: op: Literal["accept","decline","cancel","end","respond","ready","pause","resume","leave","join","feedback"]
                 actor: UUID; round: int | None = None; payload: Mapping[str, Any] = field(default_factory=dict)
  class MachineError(Exception): code: str; status: int
  def apply(state: SessionState, cmd: Command, now: datetime) -> SessionState   # returns new state; raises MachineError
  def tick(state: SessionState, now: datetime) -> SessionState | None          # deadline-driven transitions
  def deadline(state: SessionState, now: datetime) -> datetime | None
  ```
  Kind-specific behavior is delegated to `icebreaker.py`, `quiz.py`, `focus.py` (stubs raising `MachineError("NOT_IMPLEMENTED", 501)` until E/F/G).
- **Tests first (T-ACT-01):** table-driven: allowed transitions from [06 §2](../productization/06-shared-activities-design.md#2-common-state-machine) (accept by invitee only, cancel by inviter only, decline by invitee only, end by either while active/paused); forbidden ones raise with codes `WRONG_ACTOR`/`ACTIVITY_CHANGED`; terminal states immutable; `tick` expires invites after 10 min and idle turn-based sessions after 24 h; `deadline` computed correctly.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE-T `test_activity_machine.py`.
- **Acceptance:** T-ACT-01.
- **Rollback:** unused until D-03.

### D-03 — Activity service and lifecycle API (L)

- **Depends:** D-01, D-02
- **Files:** create `backend/app/modules/activities/{schemas.py,service.py,routes.py,projection.py}`; modify `backend/app/main.py` (include router), `backend/app/core/config.py` (`activities_enabled: bool = False`, `activity_kinds: list[str] = ["icebreaker","coop_quiz","focus"]`), `backend/.env.example`, `deploy/runtime.env.example`. Create `backend/tests/test_activities_api.py`, `backend/tests/activity_helpers.py`.
- **API contract:** `GET /connections` adds `ConnectionView.activeActivity: "icebreaker"|"coop_quiz"|"focus"|null` (kind of the connection's non-terminal session; one grouped query). Catalog, invite, current, history, get, accept, decline, cancel, end, feedback per [06 §8](../productization/06-shared-activities-design.md#8-api-endpoints-and-dtos). Disabled flag → catalog `[]`, writes 503 `ACTIVITIES_DISABLED`; kind not in `activity_kinds` → 422.
- **Interfaces:** `@asynccontextmanager async def activity_transaction(request, actor, session_id)` yields `(db, user, peer, room, session_row)` with the lock order in [06 §10](../productization/06-shared-activities-design.md#10-postgresql-transactions-idempotency-and-concurrency); `project(session, participants, responses, viewer_id, now) -> ActivitySessionView` (only path to DTO).
- **Rate limits (T-ACT-05):** ≤6 invites per connection per hour, ≤20 per user per day, 10-min cooldown per (inviter, connection, kind) after decline → 429 with `Retry-After`.
- **Tests first:**
  - T-ACT-02: concurrent invites A↔B → one 201, one 409 with `currentSessionId`; accept vs cancel race → exactly one terminal outcome; replay with same `Idempotency-Key` returns identical body; stale `expectedVersion` → 409.
  - Authorization: C → 404/403 everywhere; ended room → 403.
  - T-ACT-05 quotas/cooldown; T-ACT-06 feedback only after completion and never in peer projection (use a test-only definition completed through the machine, or complete an Icebreaker once E-02 lands — mark that case `xfail(strict=True)` until E-02).
  - `room.activity_seq` increments on every mutation.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-ACT-02, T-ACT-05, T-ACT-06 (partial).
- **Rollback:** `ACTIVITIES_ENABLED=false`.

### D-04 — SSE `activity_changed` and polling contract (S)

- **Depends:** D-03
- **Files:** `backend/app/modules/social/notifications.py` (watermark `(next_seq, version, activity_seq)`; emit `activity_changed` envelope `{version:"social-events-v2", eventId:"{cid}:a{activity_seq}", connectionId, activitySeq}`), `backend/tests/test_notifications.py` (new cases).
- **Tests first:** open stream; invite → `activity_changed` within 2 s; message send still emits `messages_available` only; block → `access_revoked`.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE.
- **Acceptance:** T-ACT-03 (backend part).
- **Rollback:** revert (clients fall back to polling).

### D-05 — Lifecycle hooks, retention, export, deletion (M)

- **Depends:** D-03
- **Files:** create `backend/app/modules/activities/hooks.py` (`abort_for_pair(db, pair_id, reason)`, `abort_for_user(db, user_id, reason)`, both bump `activity_seq`; **lock order:** lock the affected `connections` rows first (`ORDER BY id FOR UPDATE`), then the sessions — never a session before its room — so hooks cannot deadlock with route writes or the sweeper); call from `backend/app/modules/social/routes.py` (`block_peer`, `end`), `backend/app/modules/social/service.py` (`interaction()` whenever it closes a room → `abort_for_pair(pair.id, "consent_withdrawn" if snapshots == {} else "room_closed")`; this also covers MATCH withdrawal and deletion, which close rooms through `invalidate_user_social` → `interaction`), `backend/app/modules/users/lifecycle.py` (`matching` scope: abort + delete own responses + null own feedback), `backend/app/jobs/retention.py` (delete responses > 90 days, terminal sessions > 90 days after `ended_at`), `backend/app/modules/users/export.py` (`social.activities`: own sessions, own responses, own feedback), `frontend/src/features/real/RealApp.tsx` (MATCH withdrawal copy adds "…và dừng mọi hoạt động chung đang diễn ra."). Create `backend/tests/test_activity_lifecycle.py`.
- **Tests first (T-ACT-04, T-PRIV-01 part):** block / end / MATCH off / account deletion each abort an active session with the right `end_reason` and deny further reads; retention purges old rows only; export contains own answers and excludes peer answers.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE.
- **Acceptance:** T-ACT-04; export/deletion part of T-PRIV-01.
- **Rollback:** revert hooks (sessions would then expire via deadlines).

### D-06 — Deadline sweeper (S)

- **Depends:** D-03
- **Files:** create `backend/app/modules/activities/jobs.py` (`async def advance_due(app, now=None) -> int`, algorithm in [06 §10](../productization/06-shared-activities-design.md#10-postgresql-transactions-idempotency-and-concurrency)); modify `backend/app/main.py` (`sweep_context` calls it every loop inside the existing try/except). Create `backend/tests/test_activity_sweeper.py`.
- **Tests first:** invite older than 10 min → `expired` + `activity_seq` bumped; concurrent accept and sweep (gather) → one consistent outcome (accept wins if committed first; otherwise 409); room locked by another transaction → skipped and processed next tick.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE.
- **Acceptance:** T-ACT-02 (sweeper race).
- **Rollback:** revert call in `main.py`.

### D-07 — Frontend activity infrastructure (L)

- **Depends:** D-04, A-03
- **Files:** create `frontend/src/features/real/social/useConnectionEvents.ts` (move SSE + polling logic out of `HumanChat`, expose callbacks `onMessages`, `onActivity`, `onRevoked`), `frontend/src/features/real/activities/{useActivity.ts,ActivityEntryButton.tsx,ActivityCatalog.tsx,InviteCard.tsx,ActivityDock.tsx,ActivitySummary.tsx,FeedbackChips.tsx,clock.ts,activities.css,activityView.ts}` and tests `activityView.test.ts`, `clock.test.ts`; modify `frontend/src/features/real/Social.tsx` (`HumanChat` uses the hook and hosts the dock), `frontend/tests/e2e/social.spec.ts` (mocked invite/accept/decline flows).
- **Interfaces:** `useActivity(connectionId) -> {session, loading, error, refresh, act(op, body)}`; `act` sends `expectedVersion` from the latest session and maps 409 → refresh + notice. `clock.ts`: `createClock(serverTime: string, receivedAt = Date.now()) => {now(): number}`; `remainingMs(endsAt: string, clock)`. `activityView.ts`: pure helpers (`isMyTurn`, `waitingLabel`, `canInvite`).
- **Tests first:** unit tests for clock offset (server ahead/behind), `isMyTurn` matrix; mocked E2E: invite card states for inviter and invitee, decline cooldown disables entry button, 409 refresh notice.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-FE · [ ] existing chat E2E still pass (stream fallback unchanged).
- **Acceptance:** T-ACT-03 (frontend part), invite flows per [08 §6.1](../productization/08-frontend-ux-plan.md#61-invite).
- **Rollback:** revert; backend flag off hides catalog.

## Phase E — Icebreaker

### E-01 — Icebreaker content bank (S)

- **Depends:** D-02
- **Files:** create `backend/app/modules/activities/content/icebreaker_v1.json` (≥24 items: 8 per tier `light`/`curious`/`reflective`; `{id, tier, prompt, options[3–4], allowText}`; Vietnamese; no sensitive topics), `backend/app/modules/activities/content/__init__.py` (`load_bank(name) -> list[dict]` with validation), `backend/tests/test_activity_content.py`.
- **Tests first:** counts per tier, unique ids, option counts, prompt ≤ 120 chars, no option duplicates, banned-topic keyword list absent.
- **Steps:** [ ] tests fail · [ ] write content (product owner review recommended) · [ ] tests pass.
- **Acceptance:** content validated at import (startup fails fast on invalid banks).
- **Rollback:** n/a.

### E-02 — Icebreaker rules: responses, reciprocal reveal, ready (M)

- **Depends:** D-03, E-01
- **Files:** create `backend/app/modules/activities/icebreaker.py` (`on_accept` picks 1 item per tier with `random.Random(str(session_id))`; `respond`, `ready`, `project_round`); modify `machine.py` (delegate), `service.py`/`routes.py` (`POST /activities/{sid}/responses`, `POST /activities/{sid}/ready`), `projection.py`. Create `backend/tests/test_icebreaker.py`.
- **Tests first (T-ICE-01):** peer answer absent from raw JSON until both submitted; reciprocal reveal: skipper gets `peer: "hidden"`, answerer sees skipper's `"skipped"`; same payload retry → same view; different payload → 409 `RESPONSE_CONFLICT`; wrong round → 409 `ROUND_CHANGED`; advance only when both ready; after round 3 both ready → `completed`; feedback allowed now (turn the D-03 xfail into a pass).
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-ICE-01, T-ACT-06.
- **Rollback:** remove `icebreaker` from `ACTIVITY_KINDS`.

### E-03 — Icebreaker UI (M)

- **Depends:** E-02, D-07
- **Files:** create `frontend/src/features/real/activities/IcebreakerPanel.tsx` (+ test of pure helpers in `activityView.test.ts`); modify `ActivityDock.tsx`, `ActivitySummary.tsx`; `frontend/tests/e2e/social.spec.ts`.
- **Tests first:** mocked E2E: answer → waiting state; reveal both; skip → hidden-peer message; next → waiting; completion summary + feedback chips; draft text preserved across a 409 refresh.
- **Steps:** [ ] tests fail · [ ] implement per [08 §6.2](../productization/08-frontend-ux-plan.md#62-icebreaker-panel) · [ ] VC-FE.
- **Acceptance:** UI half of T-ICE-02 (full-stack in J-01).
- **Rollback:** flag kind off.

## Phase F — Cooperative quiz

### F-01 — Quiz content bank (S)

- **Depends:** D-02
- **Files:** `backend/app/modules/activities/content/coop_quiz_v1.json` (≥60 items `{id, category, prompt, options[4], correctIndex, explanation}`), extend `test_activity_content.py`.
- **Tests first:** counts, unique ids, `correctIndex ∈ 0..3`, explanation ≤ 160 chars, ≥ 5 categories.
- **Steps:** [ ] tests fail · [ ] content (fact-check each answer; cite nothing external in-app) · [ ] pass.
- **Acceptance:** validated bank.
- **Rollback:** n/a.

### F-02 — Quiz rules and cooperative scoring (M)

- **Depends:** D-03, F-01
- **Files:** create `backend/app/modules/activities/quiz.py` (pick 5 items; respond; reveal; score: +1 per correct participant, +1 bonus if both correct; mutual ready; completion after round 5), modify `machine.py`, `projection.py` (never include `correctIndex`/`explanation` before reveal). Create `backend/tests/test_quiz.py`.
- **Tests first (T-QUIZ-01):** raw JSON of every pre-reveal response lacks `correctIndex`; scoring table cases (0,0)→0, (1,0)→1, (1,1)→3, skip counts as incorrect; total ≤ 15; history after completion includes correct answers.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-QUIZ-01.
- **Rollback:** remove `coop_quiz` from `ACTIVITY_KINDS`.

### F-03 — Quiz UI (M)

- **Depends:** F-02, D-07
- **Files:** create `frontend/src/features/real/activities/QuizPanel.tsx`; modify dock/summary; mocked E2E cases.
- **Tests first:** reveal uses icon + text (assert accessible names "Đáp án đúng", "Bạn chọn"); team score visible; summary list.
- **Steps:** [ ] tests fail · [ ] implement per [08 §6.3](../productization/08-frontend-ux-plan.md#63-quiz-panel) · [ ] VC-FE.
- **Acceptance:** UI half of T-QUIZ-02.
- **Rollback:** flag kind off.

## Phase G — Shared focus session

### G-01 — Focus timer model (pure) (M)

- **Depends:** D-02
- **Files:** create `backend/app/modules/activities/focus.py`, `backend/tests/test_focus_timer.py`.
- **Interfaces:**
  ```python
  def start(options: FocusOptions, participants: tuple[UUID, UUID], now: datetime) -> dict      # phase "starting", 5 s
  def advance(timer: dict, now: datetime) -> tuple[dict, bool]                                 # (timer, completed?)
  def pause(timer, actor, now) -> dict; def resume(timer, now) -> dict
  def leave(timer, actor, now) -> dict; def join(timer, actor, now) -> dict
  def minutes(timer: dict, until: datetime) -> dict[str, int]                                  # {"self_or_uid": n, "together": n}
  def deadline(timer: dict, now: datetime) -> datetime | None                                  # phase end, pause limit, both-away limit
  ```
- **Tests first (T-FOCUS-01):** injected clock through starting→focus→break→focus→done for 2 cycles (final break skipped); pause at 10:00 remaining then resume keeps 10:00; pause > 15 min → ended; both away 10 min → ended; minutes intersection math (presence gaps); presence capped at 20 intervals.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE-T `test_focus_timer.py`.
- **Acceptance:** T-FOCUS-01.
- **Rollback:** unused until G-02.

### G-02 — Focus endpoints and transitions (M)

- **Depends:** D-03, D-06, G-01
- **Files:** modify `machine.py` (focus delegation), `routes.py` (`/focus/pause|resume|leave|join`), `jobs.py` (focus deadlines), `projection.py` (`timer.phaseEndsAt`, presence flags, summary minutes), `backend/app/core/config.py` (`focus_test_plan_seconds: int | None = None`, honored only when `APP_ENV=test`). Create `backend/tests/test_focus_api.py`.
- **Tests first:** invite with plan/cycles validation (422 outside allowed); accept → `starting`; sweeper (with patched now) moves to focus/break/completed and bumps `activity_seq`; pause by either, resume by either; `NOT_FOCUS` on non-focus session; summary minutes equal on both projections.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** backend half of T-FOCUS-02.
- **Rollback:** remove `focus` from `ACTIVITY_KINDS`.

### G-03 — Focus UI with skew-corrected countdown (M)

- **Depends:** G-02, D-07
- **Files:** create `frontend/src/features/real/activities/{FocusPanel.tsx,FocusTimerChip.tsx}`; extend `clock.test.ts`; mocked E2E.
- **Tests first:** countdown uses server offset (mock `serverTime` 30 s ahead → remaining matches server); announces phase change via polite live region only; pause/resume buttons reflect `pausedBySelf`; summary shows factual minutes, no badge/achievement text.
- **Steps:** [ ] tests fail · [ ] implement per [08 §6.4](../productization/08-frontend-ux-plan.md#64-focus-panel) · [ ] VC-FE.
- **Acceptance:** UI half of T-FOCUS-02.
- **Rollback:** flag kind off.

## Phase H — UX/UI integration

### H-01 — Navigation badges and Discovery information architecture (M)

- **Depends:** B-05, C-07
- **Files:** create `frontend/src/features/real/social/{Discovery.tsx,useSocialSummary.ts}` (tabs via `?tab=`), modify `RealApp.tsx` (`Navigation` badges, nudge card on `/assistants` for adults without a live profile), `Social.tsx` (re-export barrel), mocked E2E.
- **Tests first:** tabs keyboard navigation (arrow keys), URL persistence, badge counts and `aria-label`s, nudge visibility rules.
- **Steps:** [ ] tests fail · [ ] implement per [08 §2](../productization/08-frontend-ux-plan.md#2-navigation) · [ ] VC-FE.
- **Acceptance:** T-UX-01 (navigation part).
- **Rollback:** revert.

### H-02 — Chat layout with activity dock and timeline cards (M)

- **Depends:** E-03, F-03, G-03
- **Files:** create `frontend/src/features/real/social/{HumanChat.tsx,HumanMessages.tsx}` (move from `Social.tsx`), modify `ActivityDock.tsx` (sheet < 1100 px / side panel ≥ 1100 px, collapsed bar, focus trap on mobile expanded), `InviteCard.tsx` (inline history: last 10 terminal sessions via `GET …/activities?limit=10` merged by time into the log), remove the `Social.tsx` barrel once imports are updated.
- **Tests first:** mocked E2E at 390 and 1280: dock modes, collapse/expand, Escape returns focus, composer visible with collapsed dock, inline summaries in log order.
- **Steps:** [ ] tests fail · [ ] implement per [08 §5–6](../productization/08-frontend-ux-plan.md#5-messages-list-and-chat) · [ ] VC-FE.
- **Acceptance:** T-UX-01 (chat part).
- **Rollback:** revert.

### H-03 — Loading, empty, error, offline states (S)

- **Depends:** H-01, H-02
- **Files:** create `frontend/src/features/real/OfflineBanner.tsx` (mounted in `Shell`), adjust Discovery/Messages/Chat/Dock components; mocked E2E state matrix (`tests/e2e/states.spec.ts`).
- **Tests first:** for each screen: loading skeleton/status text, empty copy + action, error with retry (route 500), offline banner (`context.setOffline(true)`), feature-off panel (`ACTIVITIES_ENABLED` false → catalog empty → entry hidden).
- **Steps:** [ ] tests fail · [ ] implement per [08 §7](../productization/08-frontend-ux-plan.md#7-loading-error-empty-offline) · [ ] VC-FE.
- **Acceptance:** T-UX-03.
- **Rollback:** revert.

### H-04 — Responsive and accessibility evidence (M)

- **Depends:** H-03
- **Files:** create `frontend/tests/fullstack/responsive.spec.ts` (viewports from [08 §9](../productization/08-frontend-ux-plan.md#9-acceptance-criteria-by-viewport), axe tags `wcag2a`,`wcag2aa`,`wcag21aa`, overflow check `document.documentElement.scrollWidth <= innerWidth`), screenshots into `docs/productization/screens/`.
- **Tests first:** the spec itself (initially failing where layout breaks).
- **Steps:** [ ] write spec · [ ] fix CSS until green · [ ] VC-FS · [ ] review screenshots by eye at 390/430/768/1280/1440 · [ ] restore historical baselines if rewritten.
- **Acceptance:** T-UX-02.
- **Rollback:** n/a.

## Phase I — Security, privacy and moderation

### I-01 — Migration `0014_moderation` and moderation API (L)

- **Depends:** D-01
- **Files:** create `backend/alembic/versions/0014_moderation.py`, `backend/app/modules/moderation/admin_routes.py`, `backend/app/modules/moderation/staff.py` (`require_staff(role="moderator")` dependency: re-reads `staff_roles`, requires `reauthenticated_at` < 12 h, 404 when `MODERATION_ADMIN_ENABLED=false`), `scripts/grant_staff_role.py` (local/test only; refuses non-local DB URLs); modify `backend/app/modules/moderation/models.py` (`StaffRole`, `ModerationAction`, report columns), `backend/app/infrastructure/database/models.py` (`User.social_restricted_until`, `User.suspended_until`), `backend/app/contracts.py` (`SessionView.staff`, `notices`), `backend/app/modules/auth/routes.py` (`session_view`), `backend/app/main.py` (include admin router), `backend/app/core/revisions.py` (append `"0014_moderation"`, drop `"0012_matching_v2"`), `scripts/apply_supabase_review.py` (`"0014"` plan, `tables=("staff_roles","moderation_actions")`), `backend/app/core/config.py` (`moderation_admin_enabled`), `backend/app/jobs/retention.py` (purge `reports` and `moderation_actions` older than 1 year — no report retention exists today). Create `backend/tests/test_moderation_admin.py`.
- **API contract:** [07 §3.4](../productization/07-database-and-api-contracts.md#34-moderation-i).
- **Tests first (T-MOD-01):** non-staff → 403 `STAFF_REQUIRED`; flag off → 404; claim → `in_review` (CAS); resolve with each action writes `moderation_actions` and sets report `resolved`/`resolution`; stale version → 409 `REPORT_CHANGED`; admin view exposes evidence but no emails/user ids (opaque refs).
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-MIG · [ ] VC-SQL `0013_shared_activities:0014_moderation 0014` · [ ] VC-CONTRACT · [ ] VC-BE.
- **Acceptance:** T-MOD-01; T-MIG-01 (local).
- **Rollback:** `MODERATION_ADMIN_ENABLED=false`.

### I-02 — Admin moderation screen and runbook (M)

- **Depends:** I-01, A-03
- **Files:** create `frontend/src/features/real/admin/Moderation.tsx` (route `/admin/reports` registered only when `session.staff`), `docs/productization/runbooks/moderation.md` (triage steps, action guidelines, escalation contacts placeholder for Q-03, 48 h SLA); mocked E2E `tests/e2e/admin.spec.ts`.
- **Tests first:** non-staff session → route redirects to `/assistants`; staff sees queue, claims, resolves with confirmation dialog; errors shown.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-FE.
- **Acceptance:** PR-S-01 UI.
- **Rollback:** flag off.

### I-03 — Enforcement: suspension and social restriction (M)

- **Depends:** I-01, C-04, D-05
- **Files:** `backend/app/core/security.py` (`verify_session`: `suspended_until > now` → 403 `ACCOUNT_SUSPENDED`), `backend/app/modules/auth/routes.py` (`login`: same check after the user row is loaded — today it only checks `status != "active"`), `backend/app/core/security.py` (`assert_purpose("MATCH")`: restricted → 403 `SOCIAL_RESTRICTED`), `backend/app/modules/social/service.py` (`match_consent` treats restricted as unavailable), `backend/app/modules/social/retrieval.py` (exclusion line), `backend/app/modules/moderation/admin_routes.py` (resolve actions: suspend → bump `auth_version`, revoke sessions, `invalidate_user_social`, `abort_for_user`; restrict → `invalidate_user_social`, `abort_for_user`; lift clears). Create `backend/tests/test_enforcement.py`.
- **Tests first (T-MOD-02):** suspended user: existing cookie → 401/403, login → 403; open SSE stream receives `access_revoked` within 6 s; restricted user absent from candidates, cannot request/message/invite (403), existing rooms closed; lift restores discovery after republish.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-BE.
- **Acceptance:** T-MOD-02.
- **Rollback:** revert; unset columns via admin lift.

### I-04 — Activity answers as report evidence; privacy coverage (S)

- **Depends:** E-02, F-02, I-01
- **Files:** `backend/app/modules/moderation/schemas.py` (`ReportInput.selected_activity_responses: list[ActivityResponseRef] ≤2`), `backend/app/modules/moderation/routes.py` (validate the responses belong to the pair's sessions; copy `{sessionId, round, kind, prompt, text|choiceLabel}` into evidence; set `connection_id`), `backend/app/modules/users/export.py` (read markers in `social`), `backend/app/modules/users/lifecycle.py` (delete own `connection_reads`), `frontend/src/features/real/Safety.tsx` (evidence picker lists revealed activity answers from the peer). Create `backend/tests/test_report_activity_evidence.py`.
- **Tests first (T-MOD-03, T-PRIV-01):** foreign session response → 403 `EVIDENCE_DENIED`; > 2 → 422; evidence text copied; export includes reads; deletion removes reads.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE · [ ] VC-FE.
- **Acceptance:** T-MOD-03, T-PRIV-01.
- **Rollback:** revert.

### I-05 — AI daily quota and global spend ceiling (S)

- **Depends:** A-01
- **Files:** `backend/app/core/config.py` (`ai_daily_turns_per_user: int = Field(60, ge=1, le=1000)`, `ai_daily_budget_usd: float = Field(0, ge=0)`), `backend/app/ai/persistence.py` (`admission`: count today's runs in Asia/Bangkok; if budget > 0 and accounting enabled, sum `AiUsage.estimated_nano_usd` since UTC midnight → 503 `AI_BUDGET_EXHAUSTED`; log `metric=ai_budget_ratio` at ≥ 0.8), `backend/app/contracts.py` + `backend/app/modules/auth/routes.py` (`FeatureView.ai_quota_remaining`), `frontend/src/features/real/RealApp.tsx` (show remaining when ≤ 10 and friendly error), env examples. Create `backend/tests/test_ai_quota.py`.
- **Tests first (T-AIQ-01/02):** 60 runs seeded today → next 429 `AI_DAILY_QUOTA`; runs from yesterday (Bangkok) don't count; budget reached → 503; budget 0 → disabled; accounting disabled → quota still enforced, budget ignored with a startup warning log.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-CONTRACT · [ ] VC-BE · [ ] VC-FE.
- **Acceptance:** T-AIQ-01, T-AIQ-02.
- **Rollback:** raise limits via env.

### I-06 — PII advisory in human chat (S)

- **Depends:** A-02
- **Files:** create `frontend/src/features/real/social/pii.ts` (`looksLikeContact(text): boolean` — Vietnamese phone patterns `(\+84|0)\d{9,10}`, emails, URLs) + `pii.test.ts`; modify `HumanChat` composer (dialog per [08 §5](../productization/08-frontend-ux-plan.md#5-messages-list-and-chat)).
- **Tests first (T-SAFE-01):** unit matrix (true/false cases incl. dates and prices that must not trigger); mocked E2E dialog flow.
- **Steps:** [ ] tests fail · [ ] implement · [ ] VC-FE.
- **Acceptance:** T-SAFE-01.
- **Rollback:** revert.

### I-07 — Operations: metrics log lines, alarms, backup/restore runbook (M)

- **Depends:** A-01
- **Files:** backend log lines listed in [09 §12](../productization/09-security-privacy-operations.md#12-logging-and-monitoring) (activities, quota, moderation, `sse_streams_open` sampled in `sweep_context` every 60 s), `deploy/aws/cloudwatch-agent.json` (log group retention 30 days), create `deploy/aws/cloudwatch-alarms.json` (metric filters + alarms; parsed by a test), `docs/productization/runbooks/backup-restore.md` (weekly dump, encryption, quarterly drill into `restore_test`), `docs/productization/runbooks/incident.md`. Create `backend/tests/test_ops_config.py` (JSON parses; every alarm references an existing metric filter; log lines contain no IDs — caplog checks).
- **Tests first:** the config test; caplog assertions for new metric lines.
- **Steps:** [ ] tests fail · [ ] implement · [ ] perform a local restore drill: `pg_dump` of a populated local `prod_e2e_test` → restore into `restore_test` → compare counts; record in `docs/productization/evidence/restore-drill.md`.
- **Acceptance:** T-OPS-01 (local drill; hosted drill requires approval).
- **Rollback:** n/a.

### I-08 — Privacy notice and provider disclosure draft (S)

- **Depends:** A-01
- **Files:** create `docs/productization/privacy-notice-draft.md` (Vietnamese; purposes, data categories, providers OpenAI/Voyage/Supabase/AWS with processing purpose, retention table from [09 §10](../productization/09-security-privacy-operations.md#10-data-retention-target), rights: export/delete, contact, age policy, moderation); link it from the in-app Settings footer only after legal approval (separate later task).
- **Tests first:** T-DOC-01 checklist in the doc header.
- **Steps:** [ ] draft · [ ] owner review requested (external) .
- **Acceptance:** T-DOC-01; legal sign-off tracked as gate G8.
- **Rollback:** n/a.

## Phase J — Full-stack testing and release qualification

### J-01 — Full-stack two-user journeys (L)

- **Depends:** H-04, I-03, I-04
- **Files:** extend `frontend/tests/fullstack/helpers.ts` (`twoUsers()`, `openRoom()`), create `frontend/tests/fullstack/{activities.spec.ts,matching-v2.spec.ts,moderation.spec.ts}`; extend `backend/tests/e2e_server.py` if a staff-grant helper or `FOCUS_TEST_PLAN_SECONDS` is needed (test-only).
- **Tests:** T-UX-01 journey; T-ICE-02; T-QUIZ-02; T-FOCUS-02 (1-minute test plan); T-ACT-03 stream drop + reload resume; block mid-activity closes peer dock; matching v2 with 6 synthetic users (labels/reasons, no percentages); moderation resolve → restricted user loses discovery; T-REG-01 (all existing specs).
- **Steps:** [ ] write specs · [ ] VC-FS until green (do not edit `frontend/` during runs) · [ ] record results in `docs/productization/evidence/fullstack.md`.
- **Acceptance:** all listed tests pass; no historical baseline changes committed.
- **Rollback:** n/a.

### J-02 — 50-user load qualification (M)

- **Depends:** J-01
- **Files:** extend `scripts/load_social_mood.py` (per pair: one Icebreaker through completion; unread/summary polling; candidates under v2), `docs/productization/evidence/load-50.json`.
- **Steps:** [ ] VC-DB `prod_load_test` · [ ] `cd backend && uv run --locked python ../scripts/load_social_mood.py --users 50 --think 1 --output ../docs/productization/evidence/load-50.json` (always pass `--output`; the default writes into `docs/mvp-validation/`).
- **Acceptance:** T-PERF-01: writes p95 < 800 ms, reads p95 < 500 ms, 0 unexpected HTTP, 0 integrity failures (duplicate sessions, leaked answers, seq gaps).
- **Rollback:** n/a.

### J-03 — Hosted migration review package (M, **approval-gated apply**)

- **Depends:** I-01
- **Files:** `docs/productization/migrations/{0011,0012,0013,0014}-review.sql` (+ SHA-256 in `docs/productization/migrations/README.md`), rehearsal reports `00NN-rehearsal.json`.
- **Steps:** [ ] operator takes a fresh `pg_dump --schema=moodprint` of hosted (approval) · [ ] restore into local `hosted_snapshot_test` · [ ] `apply_supabase_review.py --upgrade 00NN --rehearse-url <local>` for each in order · [ ] **stop and request approval** with hashes · [ ] on approval only: apply each, run `scripts/inspect_database.py`, Supabase advisors (read-only), record execution JSON.
- **Acceptance:** T-MIG-01 complete; hosted at `0014_moderation` only after approval.
- **Rollback:** see [11 §5](../productization/11-migration-and-rollback.md#5-rollback-strategy).

### J-04 — Staging deploy and rollback rehearsal (M, **approval-gated**)

- **Depends:** J-03, J-02
- **Prerequisites:** Q-06 resolved (AWS resources, domain, GitHub `staging` environment reviewer), SMTP (Q-05).
- **Steps:** [ ] merge reviewed branch to `main` (user approval) · [ ] CI green on SHA · [ ] run `deploy-staging.yml` with typed approval · [ ] smoke ([12 §4](../productization/12-release-readiness.md#4-launch-day-checklist)) · [ ] redeploy previous digest (rollback rehearsal) · [ ] record evidence.
- **Acceptance:** T-OPS-02.
- **Rollback:** previous image digest.

### J-05 — Release readiness decision (S)

- **Depends:** J-04, C-06, I-08
- **Files:** create `docs/productization/evidence/release-readiness-<date>.md` filling every gate in [12 §2](../productization/12-release-readiness.md#2-gono-go-gates-all-must-be-pass-with-evidence-links) with PASS/FAIL/BLOCKED and links.
- **Acceptance:** T-REL-01; overall status PASS only if all gates PASS; otherwise PARTIAL/HOLD with owners.
- **Verify / expected:** `grep -cE "\| G(1[0-2]|[1-9]) \|" docs/productization/evidence/release-readiness-<date>.md` → 12 (every gate row present), and every row has PASS/FAIL/BLOCKED plus an evidence link.
- **Rollback:** n/a.

## Self-review (planning session)

- Spec coverage: every requirement in [03 §7](../productization/03-product-requirements.md#7-traceability-requirement--tasks--tests) maps to ≥1 task above; every task has acceptance + verification.
- Names consistent across tasks: `pair_alias`, `room_gate`, `consent_view`, `READY_REVISIONS`, `activity_seq`, `activity_transaction`, `project`, `advance_due`, `MATCHING_SCORER`, `ACTIVITIES_ENABLED`, `ACTIVITY_KINDS`, `MODERATION_ADMIN_ENABLED`, `AI_DAILY_TURNS_PER_USER`, `AI_DAILY_BUDGET_USD`.
- Migration chain: 0010 → 0011 (B-04) → 0012 (C-02) → 0013 (D-01) → 0014 (I-01); each task updates `backend/app/core/revisions.py` (keeping the previous head for one release), and adds an `UpgradePlan`; the inspector reads the same constant.
- Execution choice: recommended **native execution phase by phase with a `/change-review` after each phase** (cheaper; tasks are sequential around shared files like `social/routes.py`). Subagent-driven execution is suitable for the content-bank tasks (E-01, F-01) and independent UI tasks.
