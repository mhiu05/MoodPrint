# Friendship Discovery — final QA, 2026-10-31

> Policy update, 2026-10-31: the approved global minimum is now **18+ for all MoodPrint**, including guests and personal features. Earlier 16+/teen statements below are historical audit evidence and are superseded by the [18+ rollout](../release/moodprint-18plus-0020-rollout.md). Friendship functionality and separate publication consent remain preserved.

Current release preparation on `feat/friendship-discovery-18plus`: applicable
backend **1175 passed**, staff follow-up **37 passed**, fixture browser **355 passed**,
fullstack v1 **35 passed**, v2 **10 passed**, Vitest **145 passed** and tooling
integration **1 passed**, all with zero failures/skips in those final runs.
The [current rollout report](../release/moodprint-18plus-0020-rollout.md) records
overlap, earlier failures, migration/restore proof and the functional commit manifest.
Hosted revision remains 0019; **HOSTED_MIGRATION_DEFERRED — COMPATIBLE_RELEASE_REQUIRED**.
A repository publication hold prevents premature automatic activation after merge.
The earlier session's no-push authorization statements below are historical;
the current owner request authorizes the review-branch push, while PR/merge/deploy
remain outside this session.

This report covers the recovery/completion session on `test/local-2026-10-30`.
The original implementation was retained. Historical results and the FR/NFR/PRE →
T01–T37 matrix remain in [08 implementation evidence](08-implementation-evidence.md).

**Status: READY_FOR_PR_REVIEW.** Local automated gates pass; physical-device and
screen-reader checks remain explicitly manual. This is not a production release
or authorization to open a PR.

Verified implementation commit: **`b2f04a5440da23cfab1e77c2a41781ca37de85ef`** —
`feat(friendship): finalize discovery experience and integration verification`.
The report/ledger are committed separately after that tested source snapshot;
the report commit is resolved by `git log -1 --format=%H -- docs/friendship-profile-redesign/09-final-qa-report.md`.

## Scope and recovered baseline

- Repository root `E:/MoodPrint`; initial HEAD `d6eaf71908a13d31b3d9192e59ebf2f52129811e`.
- `main` initially `5d2b384516b9318e6ee132c1a8b08dcbc374b79b`; no branch switch or integration operation.
- No staged files initially. Existing Discovery source/tests/contracts/docs were uncommitted and belong to this feature.
- Preserve unrelated dirty `RealApp.tsx`, `journal/journal.css`, unrelated companion planning directory and scratch artifacts. `.gitignore` already differs from main in committed history; this session never edits it.
- During this session an external edit added `.tmp/` to `.gitignore`. Preserve it
  unstaged, along with the two unrelated application files; do not revert it.
- Existing eight documents and actual source were re-read. Current user authorization supersedes their historical planning-only/no-commit instructions.

## Implementation and review

The existing optional discovery v1 JSONB contract, reducer, three-question builder,
live preview, explicit draft/review/publish flow, navigation guards and grounded
recommendation cards remain. No endpoints, matching inputs, canonical taxonomy,
publication minimums, age eligibility or hosted policies were changed.

Fixed keyboard removal focus in both featured trays and full-interest management:
next item → previous item → stable heading/search/action. If deleting the last
retained interest removes the management launcher, Dialog returns to the question
heading. Full deletion announces the removed label and remaining count. Three
new browser regressions were observed failing before the fix and passing after.

The eight first-screen entries are six canonical interests plus equally accessible
creativity/sports expansion buttons. Each expansion stores concrete canonical IDs,
never a made-up category ID. This matches the approved mapping decision in 03/04.

Two read-only reviews used fresh agents: backend security/compatibility and final
cross-layer source review. Neither found a confirmed important product defect.
The backend reviewer identified the exact legacy response assertion needing the
documented additive `discovery: null` member; its real DB failure was reproduced.

Final isolation review found a test depended on the unrelated `RealApp.tsx`
redirect edit: HEAD renders sign-in in place, while the dirty version redirects to
`/login`. Both clear private state correctly. The session-expiry assertions now
require Email/sign-in controls and removal of private editor/late responses. The
original URL assertion was observed failing with a read-only HEAD overlay; the new
assertions pass with both versions. An additional fullstack run overlays **both**
HEAD RealApp and journal.css through an ignored Vite test plugin, preserving import
resolution without writing either user file: v1 **7 passed**, v2 **4 passed**.

## Migration/readiness decision

`READY_REVISIONS` correctly accepts **only `0020_private_profile_retirement`**.
0020 is destructive: it deletes retired private items/proposals, expires pending
source-backed memory proposals, removes source/purpose columns and detaches
approved memories. It increments affected data versions. It does not change
friendship payloads, matching tables, journal rows, session tokens or social RLS.
Accepting 0019 would incorrectly claim compatibility with the current ORM/lifecycle.

The two reported failures were reproduced (18 passed, 12 DB-skipped, 2 failed).
Tests now reject 0019, accept 0020 and reject unknown heads. Additional stale
head assertions in real readiness/guest upgrade/rollback tests were reconciled.
Production readiness was **not relaxed**.

`test_discovery_migration.py` builds the full Alembic chain to 0019 in a unique
owned scratch DB, seeds legacy journal/auth/publication/draft/approved and pending
memory data, upgrades to head, repeats `upgrade head`, checks preservation and
intended retirement, and proves destructive downgrade is refused. Base-table RLS
comes from the separately reviewed initialization bootstrap, not Alembic 0001;
the test explicitly reproduces that baseline before asserting it survives 0020.

Future release order: plan/backup/rehearse destructive 0020 separately, stop old
backend traffic that relies on removed columns, migrate using an authorized owner,
verify head/ACL, then start the compatible backend before the new frontend. Do not
stamp a revision without running DDL. No rolling 0019/0020 compatibility window is
claimed. **No hosted Supabase connection or mutation occurred in this session.**

## Disposable DB isolation

- Docker was stopped initially; elevated read-only inventory confirmed that state.
  Docker Desktop was started locally, then a new labelled UUID container was created.
- Image `pgvector/pgvector:0.8.2-pg17`; observed PostgreSQL **17.10**, pgvector **0.8.2**.
- Container `moodprint-disposable-e6057f89fb764591a91d08eaa58cc35b`;
  bind **127.0.0.1:55439**; PostgreSQL data in tmpfs, no existing user volume.
- A random run-specific DB owner and DB name, plus DB ownership comment, distinguish
  this run. Credentials live only in an ignored `.tmp/.../.env`; no passwords in this report.
- `TEST_DATABASE_URL` is mandatory; no application/hosted URL fallback. Before reset,
  guards check URL driver/host/name/query overrides, actual loopback peer, current and
  session user, DB owner, run marker and `APP_ENV=test`. Failure prevents destructive setup.
- New scratch helper creates a unique sibling without a pre-delete; cleanup rechecks
  ownership and removes only that successfully created DB. Two older migration tests
  previously pre-deleted predictable names; they now use the owned helper. The guest
  migration review fixture uses it as well.
- Pytest and fullstack used different owned databases. Fullstack v1/v2 were sequential,
  with a fresh scratch DB per run; no concurrent reset of the same DB.

Reproduce provisioning with `backend/.venv/Scripts/python.exe scripts/disposable_postgres.py`.
Load the printed environment file locally with `dotenv_values`, set `APP_ENV=test`,
and pass only its test variables to the commands below. Never paste its credential URL
into a tracked file or terminal log. Cleanup uses `scripts/disposable_postgres.py --remove RUN_ID`,
which verifies the exact container label and tmpfs before removal.

## Test matrix

Final automated outcomes are recorded in the completion entry in 08. Commands:

| Gate | Exact command / evidence |
| --- | --- |
| Vitest | From frontend: `npm.cmd test`; `.tmp/friendship-ui-vitest.log` |
| Types/build | From frontend: `npm.cmd run typecheck`; `npm.cmd run build` |
| Fixture browser | `npx.cmd playwright test --config ../.tmp/friendship.playwright.config.ts discovery.spec.ts social.spec.ts states.spec.ts motion.spec.ts --reporter=list`; `.tmp/friendship-ui-playwright.log` |
| Full pytest | From backend: `python -m pytest tests --ignore=tests/live -m "not live" -q --tb=short -ra -o faulthandler_timeout=60 --junitxml=../.tmp/friendship-pytest-database.xml`; `.tmp/friendship-pytest-database.log` |
| Final whole suite | Same selection, plus `--durations=20`, XML `../.tmp/friendship-pytest-final.xml`: **1141 passed / 0 failed / 0 skipped**, exit 0, 929.36s. `.tmp/friendship-pytest-final.log`. |
| Backend release regression | 18 selected modules in `.tmp/run_friendship_backend.py`; **163 passed / 0 failed / 0 skipped**, exit 0. **90** actual PostgreSQL cases (including migration rehearsal), **73** cases without PostgreSQL. `.tmp/friendship-pytest-release.log` and XML. |
| Fullstack v1 | `python scripts/test_fullstack.py matching-v2.spec.ts local-mvp.spec.ts moderation.spec.ts responsive.spec.ts`; `.tmp/friendship-fullstack-v1-final.log` |
| Fullstack v2 | `E2E_MATCHING_SCORER=v2` then `python scripts/test_fullstack.py matching-v2.spec.ts`; `.tmp/friendship-fullstack-v2-final.log` |
| Committed-source isolation | HEAD RealApp/journal.css overlay: fixture suites **44 passed**, fullstack v1 **7 passed**, v2 **4 passed**, all exit 0. Logs `.tmp/friendship-fixture-head-final.log`, `.tmp/friendship-head-fullstack-v1.log`, `.tmp/friendship-head-fullstack-v2.log`. |
| Contracts | `backend/.venv/Scripts/python.exe scripts/export_openapi.py`; from frontend `npm.cmd run contracts:generate`; output hashes unchanged |
| Hygiene | `python scripts/check_docs.py`; `python scripts/check_reviewed_artifacts.py`; scoped Ruff; `git diff --check` |

The initial fullstack run was **6 passed/1 failed**, due to the new test expecting
the saved editor to auto-open after reload. The actual supported journey has an
explicit edit button. Test corrected to reopen it, retaining persistence assertions;
no product behavior or assertion was weakened. Its original log/trace remains in
`.tmp/friendship-fullstack-v1/` and `.tmp/friendship-fullstack-v1.log`.

The first full real-DB pytest run executed **1140 cases: 1138 passed, 2 failed,
0 skipped** (exit 1, 26m02s). The stale guest proposal signature was corrected;
its module then passed **4/4**, and it also passed in the 163-case release regression.
The other failure was the accounting test's 3-second wait for synthetic-model startup.
Its complete module passed **5/5** in an isolated diagnostic run without changing
assertions, timeout or production AI code (`.tmp/friendship-accounting-diagnostic.log`).
A final whole-suite run is performed sequentially, with no other DB harness running,
to distinguish a reproducible regression from contention during the earlier run.
That run passed all **1141** cases, retaining the accounting test's original
3-second timeout. No production AI behavior or timeout was changed to manufacture
a pass. Initial failures remain documented rather than discarded.
External-provider tests under `tests/live` are excluded, as required by the local,
synthetic-only scope; there are **zero skipped cases** in the applicable final run.

## Persistence, privacy, compatibility and rollback

New real DB cases cover partial private draft save/reload, actor ownership, no
publication/consent on save/preview, ten-interest preservation, old-client omission,
featured intersection, explicit null, omission/null receipt distinction, concurrent
same-version writes, expired preview, publish retry without duplicate consent or
publication, and creating a legacy draft from an existing new-format publication.

The real UI scenario additionally chooses without writes, saves an incomplete
draft, reloads/reopens it, supplements required fields, reviews without publishing,
publishes separately, finds a second synthetic member, then withdraws and verifies
removal from recommendations while retaining the private draft. Existing matching,
revocation, block/report, moderation, quota and concurrency suites exercise their
server gates. Friendship remains **registered adults 18+**, not the whole 16+ audience.

Rollback rehearsal uses an older-client-shaped payload (omitted discovery) against
the compatible backend with actual JSONB persistence; metadata and all ten canonical
interests survive. This is a contract-level frontend rollback simulation, not a
deployment of a historical frontend binary. Keep the expanded backend reader/writer
when reverting the frontend; a pre-discovery DTO backend is below the rollback floor.
No metadata deletion and no destructive SQL downgrade is an approved rollback.

RLS-enabled alone is not authorization proof: runtime policies permit trusted
backend DML; owner/pair/session/consent checks in the API enforce actor boundaries.
The migration/bootstrap/role tests and multi-actor API tests cover distinct layers.
No live member data, private journal, AI memory or real candidate was used in QA.

The final 163-case regression was repeated after strengthening T31 in the existing
v1/v2/shadow flow: mutate both users' private identity, journal, mood and approved
AI memory; save a differing peer draft; compare every returned public card field
except the deliberately rotating candidate reference; then invite/accept using
the valid reference. All pass. The canary fixture has one peer; separate existing
multi-peer ranking tests cover ordering. The AST boundary now explicitly rejects
journal model/module imports as well.

## Visual/accessibility evidence and manual limits

Chromium captures were inspected at **320, 390, 430, 768, 1024, 1280, 1440px** and
**844×390 landscape**. Desktop keeps builder/preview columns when content width permits;
tablet collapses, phone uses explicit questions/preview dialog. Eight entries wrap,
Vietnamese labels remain readable, full disclosure and bottom navigation stay reachable.
Reduced motion, forced colors, 200% text, keyboard/dialog/tab/error paths are automated.
The approved title/privacy text and conversation-starter label remain correct; forbidden
copy and fake matches are absent. No reference image was supplied for pixel comparison.

Artifacts: `.tmp/friendship-ui-final/merge-readiness-test-results/`,
`.tmp/friendship-ui-430-viewport.png`, `.tmp/friendship-ui-sports-picker.png`,
and `.tmp/friendship-fullstack-v1-final/productization/screens/`.
Agent-browser axe scans found zero violations in builder and sports picker. Fixture
builder/review scans and real responsive social/chat/moderation scans are separate checks.

**Not performed:** physical iPhone/Android, NVDA/VoiceOver, actual mobile keyboard/safe
areas and representative physical-device latency. Browser emulation is not device proof;
200% CSS text verification is not a claim of testing every browser's native zoom.

Manual procedure before release:

1. Windows + NVDA (Chrome/Firefox): Tab to Discovery, navigate native radios with arrows,
   toggle interests with Space, remove first/middle/last/consecutive chips with Enter.
   Expect next/previous/heading focus and one meaningful status announcement.
2. Open every picker/preview/exit dialog; Tab/Shift+Tab must remain inside, Escape closes,
   trigger focus returns; deleting the last retained interest returns to the stable question.
3. Review with missing fields, follow error links, save a partial draft, reload, reopen,
   complete review and publish. Screen reader must distinguish local preview, saved draft
   and visible snapshot; verify no publication before final action.
4. iOS VoiceOver/Safari and Android TalkBack/Chrome on physical 320–430px-class devices:
   complete all three questions, preview, dialogs, save/reload/publish; rotate, enlarge text,
   open software keyboard and verify bottom actions/focus are not obscured.
5. Repeat in forced colors/reduced motion and native 200% zoom; inspect long Vietnamese
   labels, chip wrapping, full public-data disclosure and recommendation action recovery.

## Git delivery

Only feature source/tests/contracts, guarded local test infrastructure and this document
set may be committed. Preserve unrelated dirty files byte-for-byte and do not stage
scratch credentials/logs/screenshots or the unrelated companion planning directory.
Implementation commit: `b2f04a5440da23cfab1e77c2a41781ca37de85ef` (46 files).
The evidence-only commit adds the nine documents here and records that exact tested
source SHA; its own SHA is provided in the final response and local Git verification artifact.
No push, PR, merge, hosted migration or deployment is authorized or performed.

Disposable cleanup completed with exit 0: the exact labelled container and its local
credential file were removed; logs/screenshots/metadata remain under `.tmp`. Owned
Vite/backend listeners were stopped. Docker's shared daemon and other user resources
were left available.

## Delivery file manifest

Implementation commit (46 files; unrelated changes excluded):

```text
.github/workflows/verify.yml
README.md
backend/app/infrastructure/database/models.py
backend/app/modules/social/routes.py
backend/app/modules/social/schemas.py
backend/app/modules/social/service.py
backend/openapi.json
backend/tests/conftest.py
backend/tests/database_target.py
backend/tests/e2e_server.py
backend/tests/test_data_lifecycle.py
backend/tests/test_database_operations.py
backend/tests/test_discovery_migration.py
backend/tests/test_discovery_profile.py
backend/tests/test_disposable_database_safety.py
backend/tests/test_foundation.py
backend/tests/test_matching_compatibility.py
backend/tests/test_matching_privacy.py
backend/tests/test_guest_cleanup_recovery.py
backend/tests/test_guest_embeddings.py
backend/tests/test_guest_migration_review.py
backend/tests/test_guest_schema.py
backend/tests/test_readiness.py
backend/tests/test_social.py
frontend/src/api/generated/schema.d.ts
frontend/src/features/real/social/CandidateCard.tsx
frontend/src/features/real/social/Discovery.tsx
frontend/src/features/real/social/FriendshipQuestions.tsx
frontend/src/features/real/social/InterestPickerDialog.tsx
frontend/src/features/real/social/ProfileEditor.tsx
frontend/src/features/real/social/ProfilePublishReview.tsx
frontend/src/features/real/social/PublicProfileCard.tsx
frontend/src/features/real/social/conversationStarters.test.ts
frontend/src/features/real/social/conversationStarters.ts
frontend/src/features/real/social/discoveryProfile.test.ts
frontend/src/features/real/social/discoveryProfile.ts
frontend/src/features/real/social/social.css
frontend/src/features/real/social/useProfileNavigationGuard.ts
frontend/tests/e2e/discovery.spec.ts
frontend/tests/e2e/friendship-fixture.ts
frontend/tests/e2e/social.spec.ts
frontend/tests/e2e/states.spec.ts
frontend/tests/fullstack/helpers.ts
frontend/tests/fullstack/matching-v2.spec.ts
scripts/disposable_postgres.py
scripts/test_fullstack.py
```

Evidence commit: the nine Markdown files `01-current-state-audit.md` through
`09-final-qa-report.md` in this directory. No scratch artifact or credential file.
