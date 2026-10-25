# MoodPrint — local product experience verification

Date: 2026-10-25. Scope: local development and disposable local PostgreSQL only.
No hosted database, live paid AI, AWS, deployment, merge or PR is authorized.

## Starting point

- Original checkout: `docs/productization-plan`, clean (`git status --short`).
- Fetched `origin/docs/productization-plan`: `486625703dbc72e7db020adfdae6a9eca4a6cd5d`.
- Isolated worktree: `.worktrees/product-experience`, branch `feat/moodprint-product-experience`.
- `.gitignore`, developer `.env` and unrelated files are unchanged.
- Workflow inspection: `verify.yml` runs disposable CI on pushes; `deploy-staging.yml`
  only accepts verified `main` pushes through `workflow_run` or an explicit dispatch.
  This feature branch cannot qualify for publication or deployment.

## Baseline and confirmed defects

| Check | Observed before implementation |
|---|---|
| Ruff / mypy | PASS, 85 source files |
| Frontend typecheck / Vitest / build | PASS, 47 tests; entry JS 486.87 kB, gzip 158.15 kB |
| Backend PostgreSQL suite | 471 passed; 2 setup/privilege failures because the initial local test role could not create scratch databases/roles |
| Existing responsive full-stack spec | 1 passed; five viewports plus 390×480, no axe violations |
| Matching browser baseline | Legacy vocabulary passed; extended vocabulary reproduced the expected failure (previously hidden by `test.fail`) |
| New matching regression before fix | FAIL: two identical published profiles with chess/anime/podcasts and study-buddy produced zero candidates under v1 |
| New branding regression before fix | 2 failed: retired name in metadata, wordmark and accessible navigation labels |
| Visual review | Short desktop pages vertically centered by `.me-page { margin: auto }`; old Me2We wordmark and favicon |
| Initial 50-user stress | 3,325 requests, no unexpected statuses or integrity failures, 25/25 rooms; latency gates failed. Ran concurrently with the backend baseline, so this is contention evidence, not an isolated before/after benchmark. |

The two privilege failures are environmental, not product defects. A dedicated
loopback-only disposable PostgreSQL container on port 17432 was created for the final
suite, including migration and runtime-role tests, without elevating access in the
developer's existing cluster.

## Product decisions and changes

- **Brand:** MoodPrint wordmark, browser title/description, accessible navigation names
  and a consistent new favicon/mark. Historical documents and technical identifiers
  (CSS class names, `me2we.css`, legacy asset URL, database/cookie names) stay compatible.
  Regression checks scan active TSX and browser metadata for retired display branding.
- **Matching:** independent rollback scorer `rules-v1.1` uses the unchanged v1 formula
  (45% exact interest overlap, 35% exact values, 20% style) with the published product
  taxonomy instead of deleting new tags. Equal-goal and language rules remain; the
  frozen oracle is unchanged. Retrieval, locked eligibility recheck, explanations,
  references and metrics use the same scorer/version. `MATCHING_SCORER=v2|shadow|v1`
  remains available; no hosted flag is changed.
- **AI:** all five assistants explain their own purpose and provide a direct link to
  the relevant real feature. Privacy copy distinguishes conversations from social
  sharing; Cầu Nối explicitly explains that AI history, moods and memories do not
  feed matching. OpenAI Agents SDK architecture is preserved.
- **Human chat:** editable opening questions prepare the composer and focus it; they
  never send automatically or manufacture a peer response.
- **Activities:** explain independent answers, reciprocal reveal, cooperative rounds
  and shared pause behavior before inviting. Completed sessions no longer produce
  the misleading claim that another activity is still running in the catalog.
- **Layout:** short pages align to the top, keeping the existing visual language.
  Honest discovery empty states acknowledge a sparse population without pressuring
  people to change their preferences.

## Verification sequence

Targeted backend matching/social/oracle tests: **90 passed**. Frontend branding and
existing units: **49 passed**. Earlier failures and their repairs are preserved here;
the authoritative final results are in the command matrix below.

## Additional issues found and repaired

- Restricted members saw the same restriction as both a session notice and a failed
  social API read. Social pages now show a clear paused state and avoid the redundant
  forbidden request; the backend still enforces access independently.
- Vite watched Playwright trace HTML inside `frontend/evidence`, causing unrelated
  pages to reload during QA. `server.watch.ignored` excludes generated evidence/cache
  folders. No test assertion or `.gitignore` entry was weakened.
- 54 source links in five historical planning documents pointed to removed prototype
  files. Links now refer to their actual archived Git blob at
  `dad0cb46bf69417a7b87e60e4e745c0a8c77df71`; content and historical claims are retained.
  `scripts/check_plans.py` now passes (12 documents, 39 tasks, 43 test IDs, acyclic DAG).
- Backend final run: **482 passed**, including real PostgreSQL migrations, authorization,
  quota, moderation, multiplayer concurrency, AI privacy and the new matching race.
- Linux-only release-poller tests fail to import `fcntl` natively on Windows. Running
  the unchanged tests in an existing network-disabled local Linux container passes
  **12/12**. No AWS action was performed.

## Performance investigation

Single-worker FastAPI, disposable local pgvector PostgreSQL, default pool 8 + 4
overflow, 50 synthetic authenticated users, no live providers. The load script drives
profiles, discovery, mutual connections, chat/idempotent retries, SSE/polling,
cross-room isolation probes, mood CRUD, consent changes and 25 Icebreakers.

Instrumentation is confined to the synthetic fixture: cumulative SQL count/time and
process CPU time, without query text, parameters or private content. Concurrent SQL
seconds are summed and are not wall time; counters include fixture startup.

The clean zero-think run before optimization used 59,463 SQL statements and 83.844
process CPU seconds over 86.87 s. A joined session/account lookup removes one
roundtrip per authenticated request. Pair transactions reuse the account row already
read under canonical gates instead of selecting/locking it twice. Discovery uses
shared account gates, which coexist across readers and still block all exclusive
profile/consent/block writers. Provider/session revocation and all live-policy checks
remain in place. The new discovery/consent race regression passes.

| 50-user zero-think run | Before | After |
|---|---:|---:|
| Requests | 3,354 | 3,339 |
| Elapsed | 86.87 s | 60.18 s |
| Throughput | 38.6 rps | 55.5 rps |
| SQL statements (includes fixture startup/SSE) | 59,463 | 52,071 |
| API process CPU | 83.844 s | 60.781 s |
| Session p95 | 2,180.3 ms | 2,049.9 ms |
| Discovery p95 | 5,469.9 ms | 2,505.7 ms |
| Message send p95 | 3,501.1 ms | 2,060.4 ms |
| Unexpected HTTP / transport exceptions / integrity failures | 0 / 0 / 0 | 0 / 0 / 0 |
| Rooms opened | 25/25 | 25/25 |
| Peak pool checked out | 12 | 12 |

The existing 500 ms read / 800 ms write p95 budgets still **FAIL** under this
synchronized burst. They are retained. API CPU saturation and the capped pool remain
local bottlenecks; this is neither a hosted failure claim nor hosted capacity proof.
Request totals vary because SSE and fallback polling are time-based. The earlier
contention/build-overlap runs remain separately recorded and are not used for this
comparison. A 1-second-think run is recorded separately after completion.

The 1-second-think run completed **3,369 requests in 106.22 s**, 25/25 rooms,
zero unexpected statuses, transport retries, flow exceptions or integrity failures.
It used 55,894 SQL statements and 77.281 cumulative API CPU seconds. Peak RAM was
not sampled. The same 8+4 connection cap was retained throughout.

| Operation | p50 | p95 | Existing budget |
|---|---:|---:|---|
| Session | 237.4 ms | 731.7 ms | FAIL, read 500 ms |
| Discovery | 507.2 ms | 923.5 ms | FAIL, read 500 ms |
| Connection invitation | 133.8 ms | 891.2 ms | FAIL, write 800 ms |
| Human message send | 321.0 ms | 728.2 ms | PASS, write 800 ms |

Other remaining over-budget p95 operations: activity answer 875.4 ms, activity poll
622.4 ms, connections 505.3 ms and message poll 679.4 ms. The load runner exits 1
when any budget fails, even with perfect functional integrity. Both zero-think and
1-second-think runs therefore remain **PARTIAL**. Results are exploratory local
measurements with scheduling variation, not a statistically established capacity SLA.

Raw comparable measurements:
[before](product-experience-load-before-clean.json),
[after](product-experience-load-after.json),
[1-second think](product-experience-load-think1.json).

The default rollback flag (`--scorer v1`, serving rules-v1.1) was also measured in
a separate clean 50-user / 1-second-think run: **3,376 requests in 109.02 s**, 25/25
rooms, zero unexpected statuses, retries, exceptions or integrity failures. It used
55,673 SQL statements and 82.906 cumulative process CPU seconds, with peak pool 12.

| Default v1.1 operation | p50 | p95 |
|---|---:|---:|
| Session | 423.3 ms | 890.0 ms |
| Discovery | 742.9 ms | 1,069.8 ms |
| Connection invitation | 109.7 ms | 1,317.1 ms |
| Human message send | 364.5 ms | 890.5 ms |

These p95 values also exceed the unchanged budgets. Full results:
[default v1.1 load](product-experience-load-v1-clean.json). An earlier v1 run overlapped
a browser reproduction and is retained only in the local cache, not used for capacity
comparison. Neither scorer is claimed to satisfy the local 50-user latency gate.

## External blockers and next stage

No hosted operation is verified or attempted. Before any staging work, obtain
separate approval and review hosted migration/runtime-role readiness, provider/SMTP
configuration, privacy/provider processing decisions, moderation ownership and the
unresolved matching preference labels. Validate capacity in an authorized staging
environment; the provisional v2 benchmark is not evidence of human preference quality.
Retain the v1.1 rollback and local-only feature-flag verification. No new migration or
hosted configuration change is required by this patch.

## Responsive regression repair

The first complete UI rerun found that the new opening questions could enlarge an
empty chat and push the composer below the viewport when an activity was open at
430×932. The fix gives human chat the actual visual-viewport height, lets the message
log shrink and scroll, and lets the activity body scroll inside its dock. The
existing composer-in-viewport assertions were retained; the focused starter test
now checks the composer is visible too. Shrinking the log also exposed an axe
keyboard-scroll finding, repaired by making both AI and human message logs focusable.
No activity state, answer visibility or synchronization behavior was changed.

Windows' auto-started Vite process left Playwright's web-server teardown waiting
after all 59 mocked tests had completed. That run is recorded as 59 passed plus a
teardown error. The repeat uses a separately started local Vite server through the
configuration's existing `reuseExistingServer` behavior, with the same tests,
assertions and timeouts. No production server is involved.

## Final local verification

Commands use the already installed Python 3.12 environment in `backend/.venv` and
the locked frontend dependencies. PostgreSQL targets were explicitly assigned to
the task-owned container at loopback port 17432, with separate `*_test` databases
for the suite, browser harness, migration chain and load driver. No developer `.env`
or real provider credentials were copied into this worktree.

| Scope / cwd | Command actually executed | Final observed result |
|---|---|---|
| Backend | `.venv/Scripts/python.exe -m ruff check app tests evals alembic ../scripts/load_social_mood.py ../scripts/test_fullstack.py` | PASS |
| Backend | `.venv/Scripts/python.exe -m mypy app` | PASS, 86 source files |
| Backend, TEST_DATABASE_URL local | `.venv/Scripts/python.exe -m pytest -q --tb=short` | PASS, **482 passed**, 449.16 s; no skipped DB checks |
| Backend, local DATABASE_MIGRATION_URL | `.venv/Scripts/python.exe -m alembic upgrade head`, `alembic current`, `alembic check` | PASS, `0014_moderation (head)`; no upgrade operations detected |
| Contracts | `.venv/Scripts/python.exe ../scripts/export_openapi.py`; frontend `npm.cmd run contracts:generate` | PASS; generated contract includes rules-v1.1 |
| Frontend | `npm.cmd run typecheck` | PASS |
| Frontend | `npm.cmd test` | PASS, **49 tests**, 10 files |
| Frontend | `npm.cmd run build` | PASS, 6.81 s; entry JS 490.12 kB / 159.22 kB gzip, CSS 38.62 kB / 8.58 kB gzip |
| Frontend, prestarted local Vite | `npm.cmd run test:e2e` | PASS, **59 tests**, 1.5 min, exit 0 |
| Backend, real local FastAPI/PostgreSQL | `.venv/Scripts/python.exe ../scripts/test_fullstack.py --reporter=list --output=.cache/product-experience-final` | PASS, **24 tests**, 4.3 min, exit 0 |
| Backend, E2E_MATCHING_SCORER=v2 | `.venv/Scripts/python.exe ../scripts/test_fullstack.py matching-v2.spec.ts --reporter=list --output=.cache/product-experience-v2` | PASS, **2 tests**, 5.9 s |
| Frontend, focused replay | `node node_modules/@playwright/test/cli.js test tests/e2e/states.spec.ts --reporter=list --output=.cache/product-experience-states` | PASS, **5 tests**; upstream offline transitions retained |
| Repository | `backend/.venv/Scripts/python.exe scripts/check_plans.py` | PASS, 12 plans / 39 tasks / 43 test IDs / 76 local links; no DAG cycle |
| Local Linux container, network disabled | `docker run --rm --network none --read-only --tmpfs /tmp --volume E:/MoodPrint/.worktrees/product-experience:/repo:ro --workdir /repo --entrypoint python moodprint-api:ci -m unittest discover -s deploy/aws/tests -v` | PASS, **12 tests**; no AWS access |
| Workflow syntax, network disabled | `docker run --rm --network none --volume E:/MoodPrint/.worktrees/product-experience:/repo:ro --workdir /repo rhysd/actionlint:1.7.12` | PASS, exit 0 |
| Review | `git diff --check`, staged credential-pattern scan and explicit path review | PASS; no `.env`, ignore-file, generated screenshot or unrelated file staged |
| 50-user load | `../scripts/load_social_mood.py --users 50` and `--users 50 --think 1` (via backend Python) | PARTIAL: integrity passes, latency gates fail as detailed above |

Two separately authenticated browser contexts verify mutual consent, human message
delivery, all three real activities, independent answers/reciprocal reveal, refresh,
SSE catch-up, reporting, blocking, identity reveal/revocation and consent withdrawal.
API/PostgreSQL tests additionally exercise concurrency, stale versions, foreign-owner
access denial, moderation enforcement and AI quotas. External models are fake SDK
providers only; these results do not establish live model quality or hosted Auth/SMTP.

The v2 benchmark still uses provisional labels and its historical frozen v1 comparator;
it is not evidence of a human-preference gain over v1.1. No quality claim is made.
No dependencies were added. The entry bundle grows 3.25 kB raw / 1.07 kB gzip from the
baseline for the added guides and UX; no LCP/INP or hosted performance claim is made.

## Rendered evidence

27 selected final screenshots are kept locally under `frontend/.cache/product-experience/`,
with logs/traces under `.cache/product-experience/` and `frontend/.cache/`. Generated
screenshots are intentionally uncommitted; the existing historical screenshots and
reports are restored after verification.

- [Before, discovery layout](../../../.cache/product-experience/before/connect-1440x960.png)
- [After, discovery layout](../../../frontend/.cache/product-experience/connect-1440x960.png)
- [Active activity and reachable composer at 430×932](../../../frontend/.cache/product-experience/chat-dock-430x932.png)
- [Collapsed activity with keyboard-height viewport](../../../frontend/.cache/product-experience/chat-dock-collapsed-390x480.png)
- [Human chat, visible message and composer](../../../frontend/.cache/product-experience/human-chat-390x480.png)
- [Activity catalog on a small-height phone](../../../frontend/.cache/product-experience/activity-catalog-390x480.png)

The synthetic population differs between before/after runs; these images establish
branding/layout changes, not recommendation quality or real-user engagement. Actual
rendering was inspected at 390, 430, 768, 1280 and 1440 px, plus 390×480. The full-stack
axe WCAG 2.1 AA assertions report no violations; keyboard focus, reduced motion,
horizontal overflow, message visibility and composer reachability pass.

## Git provenance and final assessment

The branch was created from the latest fetched base at the start of this session,
`486625703dbc72e7db020adfdae6a9eca4a6cd5d`. During verification the remote documentation
branch independently advanced to `e09a2a66a6a9c3369c45b0fffcf8cb9b734ff4ba`. Its archived
source references and deterministic offline assertions are retained in this change;
there was no merge, rebase, force-push or write to that branch. Remote main was
`dad0cb46bf69417a7b87e60e4e745c0a8c77df71`. Push is restricted to the feature branch.

Verified implementation checkpoints: `c8ffefe` (matching/queries) and `741b53c`
(product experience). The final evidence commit and verified remote tip are recorded
in the session's final report; no hosted release readiness is implied by a Git push.

**Functional status: FULLSTACK_VERIFIED. Overall: PARTIAL.** All local functional,
static, migration, browser and build checks pass. The 50-user latency gate does not.
No P0 is known in the exercised paths. Remaining P1: local capacity/latency budget.
Remaining product validation: human preference labels and owner decisions on privacy,
SMTP/provider readiness and moderation staffing. Hosted verification/deployment needs
separate explicit authorization. Stop after the feature-branch push and report.
