# 02 — Prototype Removal Inventory

Scope: identify exactly what to **DELETE**, **MIGRATE**, **REFACTOR**, **KEEP** or **KEEP_FOR_TESTS**. Nothing was deleted in this session. Execution happens in Phase A of the [implementation plan](../plans/2026-10-25-moodprint-productization-implementation.md) (tasks A-02…A-05).

Method: imports traced from the production entry [main.tsx:3](../../frontend/src/main.tsx#L3) and from every test/config entry (`vite.config.ts`, `playwright*.config.ts`, `tests/harness/*`, `src/**/*.test.ts`). A module is "production" only if reachable from `main.tsx`.

## 1. Production import graph (keep)

```
main.tsx
└── features/real/RealApp.tsx
    ├── features/real/{AIData,Auth,Eligibility,Memory,MessageMarkdown,Mood,Privacy,Safety,Social,Voice}.tsx
    ├── features/real/{audio.ts,pcm-worklet.js,real.css}
    ├── api/{client.ts,stream.ts,contracts.ts,generated/schema.d.ts}
    ├── components/UI.tsx ── companions/Avatar.tsx ── companions/registry.ts
    │                     └─ styles/App.module.css
    └── styles/{tokens.css,global.css,me2we.css}
```

`gsap`/`@gsap/react` are used by production components (`Motion`, `Dialog`, `Typing` in `components/UI.tsx`) — **keep the dependency**.

## 2. Frontend inventory

| Path | Decision | Reason / evidence | Replacement / notes |
|---|---|---|---|
| `frontend/src/App.tsx` | DELETE | Legacy shell; imported only by `tests/harness/legacy-main.tsx` | — |
| `frontend/src/pages/Chat.tsx` | DELETE after MIGRATE | Simulated peer ("Mô phỏng đối phương", [Chat.tsx:394](../../frontend/src/pages/Chat.tsx#L394)), demo composer, ACT01 panel | Migrate **interaction patterns only** (activity sheet layout, progress dots, "skip this question", stop-confirmation dialog, completion card, PII advisory dialog) into new `features/real/activities/*` and `features/real/Social.tsx` (tasks D-07, E-03, I-06). No code reuse of reducer logic |
| `frontend/src/pages/Connect.tsx` | DELETE after MIGRATE | Demo discovery with fixture candidates and `setTimeout` | Migrate the candidate-card visual pattern and activity preview copy into C-07 |
| `frontend/src/pages/Profile.tsx` | DELETE after MIGRATE | Demo sharing tab ("Dùng lựa chọn mẫu") | Migrate the "choose what to share → preview" stepper pattern into C-07 |
| `frontend/src/pages/Self.tsx` | DELETE | Demo mood page; production equivalent is `features/real/Mood.tsx` | — |
| `frontend/src/pages/Settings.tsx` | DELETE | Demo settings with demo clock/reset | Production `Settings` lives in `RealApp.tsx` |
| `frontend/src/pages/StartHome.tsx` | DELETE | Demo onboarding | Production `Eligibility.tsx` |
| `frontend/src/state/Provider.tsx` | DELETE | Demo reducer provider + mock scheduler | — |
| `frontend/src/state/reducer.ts` | DELETE | Scripted bot replies (`scriptedReply`, [reducer.ts:1](../../frontend/src/state/reducer.ts#L1)), fabricated peer activity replies ([reducer.ts:989](../../frontend/src/state/reducer.ts#L989)) | — |
| `frontend/src/mocks/demo.ts` | DELETE | Fixture loader for `?fixture=` | — |
| `frontend/src/mocks/fixtures.ts` | DELETE after MIGRATE | Fake candidates, `humanReplies` ([fixtures.ts:163](../../frontend/src/mocks/fixtures.ts#L163)), 3 demo questions ([fixtures.ts:168](../../frontend/src/mocks/fixtures.ts#L168)) | Question **ideas** may seed the server-side Icebreaker bank (E-01) after rewriting; no fake people survive |
| `frontend/src/mocks/scheduler.ts` | DELETE | Timer-driven fake replies | — |
| `frontend/src/domain/matching.ts` | DELETE | Frontend matching oracle; backend owns matching | Backend `matching/scoring.py` keeps the v1 oracle vectors |
| `frontend/src/domain/mood.ts` | DELETE | Demo mood summary | Backend `mood/service.py` |
| `frontend/src/domain/policies.ts` | DELETE | Demo consent/age policies | Backend `security.py`, `age.py` |
| `frontend/src/domain/types.ts` | DELETE | Demo state types | Generated `api/generated/schema.d.ts` |
| `frontend/src/domain/domain.test.ts` | DELETE | 65 tests of deleted demo modules | Production unit tests added in D-07/E-03/F-03/G-03 |
| `frontend/src/companions/Cards.tsx` | DELETE | Demo inline cards bound to demo state | Production cards rendered in `RealApp.tsx` |
| `frontend/src/companions/Companions.tsx` | DELETE | Demo companion page | Production `Assistants` in `RealApp.tsx` |
| `frontend/src/companions/scenarios.ts` | DELETE | Scripted AI replies | Real SDK runtime |
| `frontend/src/companions/companions.test.ts` | DELETE | 12 tests of demo reducer/scenarios | — |
| `frontend/src/companions/Avatar.tsx` | KEEP | Production (`BotAvatar`, `BrandMark`) | — |
| `frontend/src/companions/registry.ts` | KEEP | Production bot visual registry | — |
| `frontend/src/components/UI.tsx` | REFACTOR | Production, but exports legacy-only `Go`, `Badge`, `Intro`, `Tabs`, `useTab`, `Avatar` (UI), `Garden` ([UI.tsx:31](../../frontend/src/components/UI.tsx#L31)…[UI.tsx:363](../../frontend/src/components/UI.tsx#L363)) | Remove the unused exports after legacy deletion (A-03). Re-check with `tsc --noEmit` + grep |
| `frontend/src/styles/App.module.css` | REFACTOR | Used by production through `cx`; contains legacy-only classes (`activitySheet`, `simulation`, `question`, …) | Remove classes with no `cx.<name>` reference after A-02; keep any class reused by the new activity UI |
| `frontend/src/styles/me2we.css` | REFACTOR | Global; includes legacy selectors (`.shared-activity-entry`, `.activity-*`) | Prune unused selectors; new activity styles go in `features/real/activities/activities.css` |
| `frontend/src/styles/{tokens,global}.css` | KEEP | Design tokens and base styles | — |
| `frontend/src/features/real/**` | KEEP (REFACTOR where tasks say) | Production | `Social.tsx` split in D-07/H-02 |
| `frontend/src/api/**` | KEEP | Production transport and generated contracts | Regenerate after API changes |
| `frontend/tests/harness/legacy-main.tsx` | DELETE | Legacy entry | — |
| `frontend/tests/harness/vite.legacy.config.ts` | DELETE | Legacy dev server on 5175 | — |
| `frontend/playwright.legacy.config.ts` | DELETE | Runs only `journeys.spec.ts` ([playwright.legacy.config.ts:6](../../frontend/playwright.legacy.config.ts#L6)) | — |
| `frontend/tests/e2e/journeys.spec.ts` | DELETE | Exercises the prototype (fixtures, demo dismiss buttons) | Coverage replaced by `tests/fullstack/*` |
| `frontend/tests/e2e/{real,social,chat-history,auth}.spec.ts` | KEEP_FOR_TESTS | Mocked-API tests of the production app; `page.route` stubs exist **only** in tests | Extend `social.spec.ts` for new UI states |
| `frontend/tests/fullstack/**` | KEEP_FOR_TESTS | Real backend journeys with synthetic accounts | Extend in J-01 |
| `frontend/tests/supabase/journey.spec.ts`, `tests/live/ai.spec.ts` | KEEP_FOR_TESTS | Hosted/live harnesses (approval-gated) | — |
| `frontend/tests/visual-review.mjs`, `frontend/tests/screenshots.mjs` | DELETE | Drive the prototype ("Đóng giới thiệu bản mẫu", scripted reply text) with a hard-coded local Chrome path | Replace with full-stack screenshot capture in H-04 |
| `frontend/tests/production-smoke.mjs` | DELETE | Smoke-tests prototype journeys ("ACT01 completed", "reset") | `scripts/test_staging_proxy.sh` + full-stack suite |
| `frontend/evidence/legacy-results.json`, `frontend/evidence/legacy/` | DELETE | Output of the deleted legacy suite (historical copy remains in Git history) | — |
| `frontend/evidence/**` (other) | KEEP | Historical evidence; excluded from Docker (`frontend/.dockerignore`) | — |
| `frontend/package.json` | REFACTOR | `name: me2we-prototype` ([package.json:2](../../frontend/package.json#L2)); script `test:e2e:legacy` | Rename to `moodprint-web`; drop the legacy script (A-04). `package-lock.json` `name` field updates with it (no dependency change) |
| `frontend/README.md` | REFACTOR | Mentions prototype/legacy flows | Update in A-04 |

## 3. Backend inventory

| Path | Decision | Reason | Notes |
|---|---|---|---|
| `backend/app/modules/matching/scoring.py` | REFACTOR → KEEP_FOR_TESTS + rollback scorer | Production scorer today (`mock-v1`); also the v1 oracle used by `tests/test_oracles.py` | C-01 moves taxonomy constants to `profiles/taxonomy.py`; C-04 keeps `score()` as the `v1` scorer behind `MATCHING_SCORER=v1` for rollback. Rename `SCORING_VERSION` to `"rules-v1"` and align the DTO literal |
| `backend/app/modules/mood/scoring.py` | KEEP_FOR_TESTS | Only `tests/test_oracles.py` imports it (`demo_date`, `mood_summary`); production uses `mood/service.py` | No change in MVP |
| `backend/app/infrastructure/sandbox/executor.py` | KEEP (disabled) | `SANDBOX_ENABLED=false`; only `tests/test_sandbox.py` imports it | Post-MVP: delete together with its test if no tool needs it |
| `Outbox` model + writes | REFACTOR (retire) | Write-only; no consumer ([01 §2.3](01-codebase-audit.md#23-privacy-platform-and-operations)) | A-05: stop writing; retention purges existing rows; post-MVP contract migration drops the table |
| `backend/tests/fakes.py`, `tests/*_server.py`, `evals/**` | KEEP_FOR_TESTS | Synthetic fake model/servers used only by harnesses | Must never be imported by `app/` (add a guard test in A-02) |
| `backend/app/ai/prompts.py` `LEGACY_BOTS`/`LEGACY_SHARED` | KEEP | Frozen baseline for evaluation; Mây still uses `baseline` | — |

## 4. Docs and scripts

| Path | Decision | Notes |
|---|---|---|
| `docs/plans/00…10-*.md`, `docs/plans/implementation-status.md` | KEEP (historical) | `scripts/check_plans.py` validates exactly these 12 files in CI; do not rename them |
| `docs/plans/validation-artifacts/visual/*` | KEEP (historical) | Baselines rewritten by the full-stack run; restore unless intentionally updated |
| `scripts/check_plans.py` | KEEP | Still guards the legacy plan set |

## 5. Deletion safety checklist (A-02 must satisfy)

1. `git grep -n "from \"\.\./\(state\|mocks\|domain\|pages\)\|companions/\(Cards\|Companions\|scenarios\)" frontend/src` → 0 hits after deletion.
2. `npm run typecheck` → exit 0; `npx vitest run` → 12 tests pass (client 3, stream 7, audio 2) before new tests are added.
3. `npm run build` → exit 0; `grep -R "Mô phỏng\|bản mẫu\|fixture=" frontend/dist` → 0 hits.
4. `npm run test:e2e` (mocked production suite) → all pass.
5. `git grep -n "test:e2e:legacy\|playwright.legacy" -- . ':!docs'` → 0 hits.
6. No backend file changes except those listed for A-05.

## 6. Production rule after cleanup

The production app must never display fake users, fabricate partner replies, simulate successful backend operations, or fall back to demo data. Enforcement:

- Guard test (A-02): a vitest that scans `src/` for imports of `mocks/`, `fixtures`, `scenarios` and fails on any hit.
- Mocked responses exist only under `frontend/tests/**` via Playwright `page.route`.
- Backend fake model (`tests/fakes.py`) is injected only by test servers (`tests/e2e_server.py`, `evals/server.py`); a backend guard test asserts `app/` never imports `tests` or `evals`.
