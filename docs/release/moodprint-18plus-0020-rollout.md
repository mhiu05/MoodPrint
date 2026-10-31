# MoodPrint global 18+ and schema 0020 rollout

Release preparation date: 2026-10-31, Asia/Bangkok.

**HOSTED_MIGRATION_DEFERRED — COMPATIBLE_RELEASE_REQUIRED**

The feature branch is `feat/friendship-discovery-18plus`. Production remains on
its existing release; this work does not deploy, create a PR, merge or change main.
Validation and branch-delivery results are recorded below as they complete.

## Policy and existing accounts

MoodPrint now requires self-declared eligibility from age 18 throughout the
application: signup, guests, assistants and memory, journal/mood, activities,
matching, publication, connections/messages and staff functionality. Public
landing/help, health probes and static assistant/taxonomy descriptions remain
public; they provide no authenticated product actions or private content.

This is self declaration, **not government-ID verification**. The database stores
birth year, not full date of birth. A year difference of exactly 18 therefore needs
an explicit declaration that the eighteenth birthday has occurred. The UI uses
one clear 18+ checkbox and sends the boundary-year adult attestation. Neither
backend nor tests claim to derive the precise birthday from a year alone.

New inputs require `self-declared-age-v2-18plus`. Existing valid adult declarations
under `self-declared-age-v1` remain eligible, avoiding a policy-only forced
onboarding. Server checks require the adult account band plus an owner-matching,
versioned declaration with supported policy, valid birth year and nonfuture aware
timestamps. Ambiguous boundary years need an adult confirmation made no earlier
than the eighteenth calendar year. Missing/invalid evidence fails closed. Historical
`under16`/`teen` database enum labels remain for compatibility and grant no product
access. Existing accounts and their data are retained.

No JWT user metadata or client `eligible` flag authorizes access. `verify_actor`
reads the persisted declaration on protected transactions and rechecks sessions,
provider revocation, account status and ownership. AI dispatch/finalization and
background embeddings use the same adult policy. Matching checks both owner and
peer declarations before returning cards or rooms, including locked candidate
rechecks. Invalid peers disappear without deleting published profiles. A staff
role cannot override the age policy.

Existing cookies can still authenticate the owner for a restricted account view;
they cannot open product APIs. Refreshing/sliding a session never restores age
eligibility. API age denial clears private UI/pending responses, fetches fresh
session context and remounts declaration fields from the returned version.
Client guards also reject stale `teen` responses with `eligible: true`.

Signup validates a nested initial `EligibilityInput` before contacting the
provider. After email confirmation, first login still requires the application's
persisted declaration; provider metadata is not promoted into authorization.
Guest entry rejects underage/unconfirmed-boundary visitors before provider signup.
Existing guest sessions obey the same checks and their immutable trial deadline.

Vietnamese copy is consistent across landing, signup, guest and account gates:
“MoodPrint dành cho người từ đủ 18 tuổi.” and
“Bạn cần đủ 18 tuổi để sử dụng MoodPrint.”

## Secure privacy exceptions

Session inspection, age declaration, reauthentication, recovery, logout, MATCH
withdrawal and owner data export/deletion remain available through explicit
age-exempt flows. Session, CSRF/write origin, owner, idempotency, version, recent
reauthentication and guest expiry rules still apply where required by each flow.
The restricted screen exposes export and deletion rather than protected navigation.
Guests explicitly confirm export and never receive another user's social data.

The secured account export includes an additive `conversations` scope for retained
owner AI transcripts; peer transcripts and expired conversations are excluded.
The seven scope names fit the existing 64-character job field. Existing transcript
export also remains owner/session/retention protected. Account export keeps its
recent registered-user reauthentication and session-bound, expiring download.
These exceptions do not enable new journal, AI or messaging activity.

## Friendship compatibility

The three-question builder, eight initial entries, canonical interests, three
featured interests, full legacy interests, live local preview, explicit save,
server review, separate publication consent, navigation recovery, grounded
starters, v1/v2 scoring and block/report boundaries are preserved. Existing
unpublished Friendship changes were split into ten functional commits; the final
split tree exactly equals original `89158ae` tree
`90b5a556c425924b6c5ba63b4631b664eb103dd9` before adding 18+ changes.

The original branch and backup ref retain `89158ae`. Published history is not
rewritten. Unrelated `.gitignore`, journal CSS, original login redirect edits and
companion planning documents are excluded from delivery. Task changes in RealApp
are staged separately from its original unrelated redirect.

## Migration identity, impact and evidence

The detailed independent [preflight and restore report](migration-0020-preflight.md)
records commands, digests, observations and evidence hashes. Current verified
project: `roznanxbiyqybjpvtilq`, region `ap-northeast-1`, corroborated against local
configuration and the actual serving AWS runtime. Application revision table:
`moodprint.alembic_version`.

| Fact | Observed result |
| --- | --- |
| Hosted revision before / after audit | `0019_journal` / `0019_journal` |
| Source head | `0020_private_profile_retirement` |
| Private items intentionally retired by future apply | 11 rows |
| Affected users whose data version increments | 3 |
| Related source/private proposals and source memories | 0 |
| Preserved hosted objects | 6 users, 88 app sessions, 24 consents, 17 historical published snapshots, 0 journal entries |
| Currently valid hosted published snapshots | 0; historical snapshots belong to 2 owners |
| Live source revision | `5d2b384516b9318e6ee132c1a8b08dcbc374b79b` |
| Compatible serving backend | FAIL: accepts only 0019 and maps retired objects |
| Hosted mutation | NONE |
| Hosted backup/restore | NOT_PERFORMED; required before future execution |
| Synthetic dump/restore and real migration | PASS; not a hosted backup |

0020 deliberately removes obsolete private items/proposals, expires pending
source-backed proposals, detaches approved memories, removes obsolete source and
purpose metadata/constraints and increments affected data versions. Its semantics
and refusal of destructive downgrade are unchanged. No users, journal entries or
friendship profiles are deleted by this release preparation.

The synthetic archive is 188,714 bytes, SHA-256
`82f44de810df52b3e69f057eef2fdccae3f2c5281cdf70d1582b2cf3dd61e2e2`.
TOC verification, isolated restore, exact representative row hashes, normalized
RLS/ACL comparison and actual restored 0019→0020 upgrade all succeeded. The real
migration regression also verifies preservation, idempotent head upgrade and
downgrade refusal. Backup contents and credentials remain outside Git.

Hosted RLS and effective privileges were inspected on nine key tables. Browser
roles lack schema usage/table DML; the trusted runtime has its existing backend
policy without superuser/BYPASSRLS. This does not replace API authorization.

An offline-only review generator exports the real transactional Alembic migration
to [pending SQL](../../deploy/supabase/pending-review/0020/0020-review.sql), SHA-256
`2aad54136bba6256557144e8d4137476b884f70a9a4bf58dd79daf40d5648474`.
Its metadata keeps hosted execution disabled. Remote Alembic and the existing
expand-only executor remain guarded; a dedicated destructive execution path
still needs operational review before release.

## Required future rollout sequence

1. The owner reviews the branch, creates the PR and merges manually. Keep the
   repository's `deploy/guest-experience.release-hold` marker: the existing guard
   blocks automatic and manual release publication while verification CI still
   runs. This prevents the main-branch publish/poller path from activating source
   requiring 0020 before the operational window. The marker does not alter AWS.
2. Prepare and verify compatible API/web images and a reviewed 0020 operator path
   before scheduling a bounded maintenance window. The future release operator
   must pause automatic activation/polling before removing the publication hold
   or publishing the coordinated release; the current backend continues serving
   throughout backup/preparation. Remove the marker only in that separately
   reviewed release change. This session has not paused the production poller.
3. Create a fresh protected hosted backup outside Git, verify integrity, restore
   into an isolated environment and verify Auth, journal, consent, matching and
   published counts. Protect Storage objects separately. Do not assume Free-tier
   automatic backup availability. A synthetic restore cannot satisfy this gate.
4. Confirm exact target, revision, extension/ACL baseline, operator ownership,
   approved artifact hash, prepared postchecks and a ready compatible backend.
5. In the bounded window, stop/drain incompatible requests, streams and workers.
   Never apply destructive 0020 while an old backend serves or keep production
   indefinitely paused awaiting a PR. No rolling 0019/0020 window is claimed.
6. Apply the complete reviewed Alembic migration with exclusive ownership,
   transaction, lock/statement timeouts and no revision stamping.
7. Verify head, retired objects, preserved data counts, ORM queries, effective
   ACL/RLS and auth/eligibility behavior. Start the compatible API, check readiness,
   then serve its matching frontend and restore traffic. Resume automatic release
   activation only after the deployed source/image/revision and health are verified.

After committed 0020, recovery is a reviewed forward fix or a rehearsed full
restore with compatible application sequencing. Do not deploy an old 0019 backend
onto 0020 or use destructive downgrade. Reconcile revocations, deletion requests
and external Storage state before resuming from any backup.

## QA evidence and delivery

Fresh applicable non-live backend run: **1,175 passed, 0 failed, 0 skipped**,
1,583.30 seconds. Independent staff follow-up: **37 passed, 0 failed, 0 skipped**;
21 new invalid-staff cases were added after full-suite collection. Independent
matching/embedding regression: **76 passed, 0 failed, 0 skipped**. Vitest:
**145 passed**. Windows release-poller execution exposed its expected `fcntl`
platform dependency; the same suite on Linux passed **18/18**. Ruff, mypy,
actionlint, contract generation, docs and commit hygiene are checked before push.

Initial fixture browser run: **334 passed / 16 failed / 0 skipped**. Initial
fullstack v1: **22 passed / 13 failed / 0 skipped**. These are retained as failed
evidence, not counted as success. Several assertions referenced published UI names
and routes that changed before this task; tests are aligned with the actual
account/identity layout while retaining owner/data/privacy assertions. Initial
browser execution also overlapped implementation HMR and an overlay CRLF issue;
final checks run against the intended task-only source.

Final local verification:

| Gate | Passed | Failed | Skipped / not run | Evidence outside Git |
| --- | ---: | ---: | --- | --- |
| Applicable non-live backend | 1175 | 0 | 0 skipped; external live suite excluded | `backend-full.xml` |
| Staff follow-up, including 21 newly collected cases | 37 | 0 | 0 | `staff-eligibility-final.xml` |
| Independent peer/embedding regression | 76 | 0 | 0 | `security-visibility-final.xml` |
| Vitest | 145 | 0 | 0 | npm test output |
| Patched OpenAPI tooling integration | 1 | 0 | 0 | Node test in npm test |
| Complete fixture browser / axe / routing | 355 | 0 | 0 | `frontend-fixtures-verified/results.json` |
| Complete real fullstack v1 | 35 | 0 | 0 | `fullstack-v1-final/fullstack-results.json` |
| Real fullstack v2 matching + age/privacy journeys | 10 | 0 | 0 | `fullstack-v2-final/fullstack-results.json` |
| Real migration regression | 1 | 0 | 0 | `migration-rehearsal.xml` |
| Offline review package | 7 | 0 | 0 | `migration-review-package.xml` |
| Linux release controls | 18 | 0 | 0 | Docker unittest output |

Evidence paths are under `.tmp/18plus-release`. Overlapping backend runs are not
added together as distinct cases. The initial single-worker full fixture retry
hit the unchanged 600-second **suite** budget: 277 passed, 78 not run, two global
timeout errors. It was not counted as a successful suite. Isolated fixture files
now use two workers; the unchanged timeout passes all 355 cases in 510.02 seconds.
Real-database fullstack remains serial (v1 458.42 seconds; v2 85.48 seconds).

Ruff and configured mypy pass; actionlint passes; docs and the eleven pinned SQL
approval checks pass. OpenAPI regeneration is unchanged. Typecheck and production
build pass, including an overlay build of intended committed source that excludes
the user's unrelated RealApp/journal edits.

Dependency audit initially found three Moderate findings through the generator's
old minimatch dependency ([advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)).
A scoped override uses patched `minimatch 11.0.1` while retaining OpenAPI-TS 7.13.0.
A process-local CommonJS adapter preserves Redocly 1's callable API; it edits no
third-party files and does not run in the browser. Its real URL/header-glob test
was observed failing before the adapter and passing afterward. Actual generated
declarations remain byte-identical; `npm audit --audit-level=low` reports **0**.

Gitleaks v8.30.1 scans the branch's added history with redaction. One exact
documentation-prose fingerprint in commit `27d6de1`, implementation plan line 220,
was manually verified as a false positive and recorded outside Git; all remaining
rules/findings stay enabled. No real credential finding is accepted. Final scan
and Git integrity results are checked again before push.

Four independent-review Medium findings were reproduced and fixed: guest export
behind the age gate, an aborted-probe refresh race, stale declaration form state,
and staff age bypass. The relevant regressions pass. No confirmed Critical/High
implementation defect remains. Physical devices and screen readers were not
tested; browser emulation and automated accessibility are not physical-device proof.

All owned test containers and their credential files were removed with guarded
UUID/label/tmpfs checks. Synthetic restore archives and sanitized evidence remain
outside Git. Public HTTPS live/ready probes still return 200 after local work.

## Branch delivery verification

Review branch: [feat/friendship-discovery-18plus](https://github.com/mhiu05/MoodPrint/tree/feat/friendship-discovery-18plus).
The original `test/local-2026-10-30` remains at `89158ae`; its remote remains at
`d6eaf71`. The backup ref is `backup/friendship-18plus-before-20261031`.
Main was observed at `5d2b384516b9318e6ee132c1a8b08dcbc374b79b`; this session does
not change it. No PR, merge, force-push or application deployment is performed.

The final response records the delivered local/remote SHA and actual CI result.
Do not infer GitHub CI success from the local results above. Reproduce delivery:

```text
git log --reverse --format="%h %s" d6eaf71..HEAD
git rev-parse HEAD
git ls-remote --heads origin refs/heads/feat/friendship-discovery-18plus
gh run list --repo mhiu05/MoodPrint --branch feat/friendship-discovery-18plus
```

The first pushed workflow, [41197762668](https://github.com/mhiu05/MoodPrint/actions/runs/41197762668),
passed backend checks (**1197 passed, 0 failed, 1 skipped**), migration/load,
frontend checks (**145 Vitest + 1 tooling + 355 browser passed**), real fullstack
(**35 passed**), SQL/documentation/release controls and actionlint. Its single
skipped test is the opt-in hosted guest compatibility test without an approved
non-production target; it is not counted as a pass. The workflow then **failed**
while building the standalone frontend image: a source-adjacent unit test imports
the authoritative backend taxonomy outside that image's build context. The
combined SPA/API image has the same boundary, so both image variants are checked
for the correction.

The correction adds a production TypeScript configuration for application source.
The existing full `npm run typecheck` and all taxonomy-backed unit/browser tests
remain enabled in CI; `npm run build` checks production source before bundling.
No timeout, assertion, taxonomy fixture or privacy check is weakened. Both the
standalone web image and combined SPA/API image build successfully from the
intended committed-source overlay. Their static-file/source-map and unprivileged
runtime/no-env checks pass. Full typecheck, 145 unit tests, the tooling regression
and production build also pass after the correction. Image IDs and smoke results
are retained in `image-build-final-results.json` outside Git. The final CI rerun
result is recorded in the delivery response.

The functional commit manifest follows. The final packaging correction is
identified by the current branch history and delivery SHA (a document cannot
contain its own Git object ID).


| Commit | Functional purpose |
| --- | --- |
| `8c82746` | test(database): add owned disposable PostgreSQL integration harness |
| `ff4d1ec` | test(readiness): require schema 0020 and rehearse private profile retirement |
| `8796cc1` | feat(friendship-api): preserve discovery metadata and legacy payloads |
| `bb24628` | feat(friendship-ui): add three-question builder and canonical interest controls |
| `f259e66` | feat(friendship-preview): add local public card and explicit publication review |
| `79f0330` | fix(friendship-navigation): save explicit drafts and recover interrupted editing |
| `58ef07a` | feat(friendship-matching): ground recommendation cards and conversation starters |
| `ee8b03e` | feat(friendship-discovery): integrate builder and publication lifecycle |
| `7062296` | test(friendship): verify browser accessibility and fullstack persistence |
| `27d6de1` | docs(friendship): preserve design decisions and verified QA evidence |
| `364329c` | feat(auth): require global 18plus eligibility and preserve account data rights |
| `c61b2f6` | fix(eligibility): recheck adult declarations for social peers and AI memory jobs |
| `cfcfc91` | fix(moderation): prevent staff roles from bypassing global age policy |
| `6b1c718` | feat(migrations): prepare guarded offline 0020 retirement review package |
| `a3c235a` | feat(onboarding): apply Vietnamese 18plus gates to signup guests and active sessions |
| `717a8a4` | chore(release): hold publication until the compatible 0020 rollout is ready |
| `db5cfcd` | test(eligibility): verify age denial and align complete browser and fullstack journeys |
| `7bbd39b` | fix(tooling): patch minimatch without changing generated API contracts |
| `cb1fe5d` | docs(release): record 18plus QA and the guarded 0020 rollout dependency |
