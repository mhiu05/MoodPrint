# AI context privacy P0 — F03 implementation

26/10/2026 (Asia/Bangkok). Implements the first remediation of the historical
[conversation audit](../ai-agent-conversation-audit.md). **Implementation: PASS
on disposable local verification; production behavior is unverified.** No merge,
deployment, hosted migration, real user records, or paid model calls were performed.

## Confirmed root cause and behavior

Previously, `conversation_view` served both the owner-visible transcript and the
runtime's model context. Memory retrieval rechecked MEM consent, but saved bot
text and user copies could still carry the withdrawn memory into the next SDK
request. Removing a retrieval tool did not remove those derivatives.

The runtime now constructs a separate model projection before memory retrieval
and model execution. It keeps only a contiguous suffix whose turns have a known
policy stamp and the current owner's `data_version`. It stops at the first
unknown policy, missing stamp, different data version, or previous mood-scoped
turn. It excludes the entire older prefix, including both user and bot messages;
it never edits the saved transcript or treats old prose as authorization.

| Transition | Model input now | Saved history |
|---|---|---|
| MEM withdrawal | Earlier epoch and its derivatives excluded; no new memory retrieval | Owner can still read/export |
| Memory correction/deletion or private-source edit/deletion | Earlier epoch excluded; retrieval checks current approved sources | Original messages retained |
| AI or history preference withdrawal/regrant | Consent/preference changes advance the durable data version; old context stays excluded | Existing management permissions retained |
| MEM regrant | Old transcript stays excluded; existing approved memories may be **freshly retrieved under the new authorization**, as before | Original messages retained |
| Mood scope absent on a follow-up | Previous mood-bearing turn and older prefix excluded; mood tool unavailable | Earlier statistics remain viewable |
| Mood scope selected again | Fresh authorized tool read; no reuse of the old mood-bearing transcript, even for identical dates | Original messages retained |
| Legacy/unknown provenance | Excluded from model input, without a permissive backfill | Read/export unchanged |
| Restart/new session/other worker | Saved turns reload their durable stamps; no RAM-only privacy boundary | Owner isolation retained |

The existing authenticated mutations advance the monotonic owner data version
for consent, preferences, memory, mood, and source changes. Existing actor,
session, deletion-pending, worker lease, cancellation, per-model-call and final
policy fences remain active. Direct administrative database edits must preserve
that versioning invariant; this change does not introduce database triggers or
claim safety for arbitrary out-of-band rewrites/restores.

## Implementation and runtime states

| File | Change |
|---|---|
| [context.py](../../backend/app/ai/context.py) | Content-free `ContextStamp`, conservative projection, typed source state |
| [chat_routes.py](../../backend/app/ai/chat_routes.py) | Stamp accepted turns transactionally; record the matching temporary-chat stamp |
| [models.py](../../backend/app/ai/models.py), [store.py](../../backend/app/ai/store.py) | Durable policy column and RAM metadata |
| [persistence.py](../../backend/app/ai/persistence.py) | Reload bounded stamps by both owner and conversation |
| [runtime.py](../../backend/app/ai/runtime.py) | Recheck current policy, project history, retrieve authorized memory, track read outcomes |
| [0015 migration](../../backend/alembic/versions/0015_context_privacy_context_privacy.py), [revisions.py](../../backend/app/core/revisions.py) | Add nullable stamp; require the schema before readiness succeeds |

`LiveRun.sources` separates authorization (`no_current_authorization`,
`authorized`, `revoked`), earlier authorization (`previously_authorized` versus
`missing_verified_evidence`), and evidence (`missing_verified_evidence`,
`tool_unavailable`, `tool_execution_failure`, `retrieved`). An empty successful
read has `retrieved` and `record_count=0`. These are internal, content-free states;
they neither grant permission nor change the public `AiOutput`/SSE contracts.

Only `text-v1` and `mood-turn-v1` are recognized policy stamps. No mood dates,
scores, memory text, tool results, or persistent snapshots are added to storage.
Old rows remain NULL, because a current data version alone cannot prove that a
legacy turn filtered its own inputs.

## Regression coverage and executed verification

[test_context_privacy.py](../../backend/tests/test_context_privacy.py) and
[test_context_privacy_migration.py](../../backend/tests/test_context_privacy_migration.py)
add **22 cases**. They capture actual `ScriptedModel` inputs through the real SDK
streaming adapter, FastAPI, and disposable PostgreSQL, without external AI calls.

- T01: fixed 20–26/10/2026 incident, 3 and 2 points, 2/7 records, mean 2.5,
  five missing buckets, `[scope, none, scope]`, temporary and saved conversations.
- T04/T05/T18: revoke/regrant, correction/deletion, AI/history preference cycles,
  runtime restart, other worker, new same-owner session, owner-denied read/export,
  earlier user copies and assistant derivatives, safe later suffix recovery.
- Source correction/deletion on another worker with a surviving temporary copy;
  a copy chain beyond both context and runtime pagination windows; legacy NULL
  provenance; independent authorization/read/error states.
- Migration preserves legacy transcript and ACL/RLS metadata, leaves NULL stamps,
  and prevents legacy replay after restoration. Readiness rejects older/unknown
  revisions. Existing tests cover the five personas, tools, active cancellation,
  live policy checks, auth and data isolation.

Commands below ran from `backend/` using `.venv/Scripts/python.exe`, or from
`frontend/` for npm/Playwright. `TEST_DATABASE_URL` identified only the separate
local `moodprint_privacy_p0_test` database. Credentials were handled in process
memory, not copied to artifacts. Baseline and RED failures preceded the fix.

| Command actually executed | Observed result | Exit |
|---|---|---|
| `python -m pytest tests/test_context_selection.py tests/test_sdk_adapter.py -q` (baseline) | 22 passed | 0 |
| Targeted baseline: persistence, memory, scoped mood, privacy lifecycle, context, SDK | 69 passed | 0 |
| `python -m pytest tests/test_context_privacy.py -q --tb=short` (corrected RED harness, before fix) | 15 replay assertions failed | 1 |
| Same initial regression file after fix | 15 passed | 0 |
| Expanded intermediate tests | 61 passed, 2 test-fixture errors; corrected payload and explicit 40-message pagination | 1 |
| `python -m pytest -q --tb=short --junitxml=../docs/ai-context-privacy-p0/backend-tests.xml` | **561 passed**, 467.97 seconds, teardown completed | 0 |
| `python -m pytest tests/test_context_privacy.py tests/test_context_privacy_migration.py -q --tb=short --junitxml=../docs/ai-context-privacy-p0/privacy-regressions.xml` (final code) | **22 passed**, 41.35 seconds; no errors, failures, skips or teardown issues | 0 |
| `python -m ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py` | All checks passed | 0 |
| `python -m mypy app` | 87 source files, no issues | 0 |
| `python -m alembic upgrade head`, then `python -m alembic check` | Separate local migration DB at 0015; no ORM drift; nullable/no-default column and RLS verified | 0 / 0 |
| `python ../scripts/export_openapi.py`; `npm.cmd run contracts:generate`; contract `git diff --exit-code` | No public schema drift | 0 / 0 / 0 |
| `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | Typecheck passed; 54 unit tests passed; Vite build passed | 0 / 0 / 0 |
| `python ../scripts/test_fullstack.py chat-history.spec.ts` | 1 real full-stack browser journey passed, desktop/mobile/keyboard/axe, clean teardown | 0 |
| `node node_modules/@playwright/test/cli.js test tests/e2e/chat-history.spec.ts --reporter=line` | 11 browser tests passed, clean teardown; mocked HTTP coverage distinguished from real integration above | 0 |

An earlier test helper used `/auth/session` instead of `/session`; it was corrected
and the complete RED run then failed on replay assertions. Windows npm forwarding
also rejected a piped grep expression (exit 1); the direct Playwright command
above replaced it successfully. Initial sandbox git/network/Docker/uv-cache
restrictions were handled with scoped authorized execution and the existing venv.
No failed command is counted as a PASS.

## Integration, rollout, limitations and rollback

- Fetched `origin` before implementation. Local `main`, local `dev`, remote
  `main`, and audited source all resolved to `779db2ac3c8013c799e38e8bd74184e83c48b826`.
  Remote has no `dev`; the Draft PR targets `main`. Implementation branch:
  `fix/ai-context-privacy-p0`. Its parent `0493225` adds only the existing audit.
- Other worktrees were preserved: `.worktrees/local-mvp` at `3a63670`,
  `.worktrees/product-experience` at `e5c8929`, and
  `E:/MoodPrint-release-integration` at `779db2a`. The pre-existing untracked
  `.worktrees/` directory and `.gitignore` were not changed.
- GitHub's latest published staging release and successful publish run
  `40265801953` identify `779db2a` (published 26/10/2026). This proves published
  provenance, **not the revision currently running on the host**. The deployed
  revision and original production incident remain unverified.
- The cutoff deliberately loses some non-sensitive continuity after unrelated
  data-version changes. It does not selectively reconstruct provenance. Current
  user text deliberately resubmitted after revocation is new user input, not
  automatic history replay. This does not erase data already sent to providers.
- F01 remains open for a reviewed follow-up/reuse authorization contract and UX.
  F02 remains open for typed evidence/source lineage, capabilities and numerical
  claim validation. No wider permission, persistent snapshot store, prompt/persona
  rewrite, real-model replay, or claim of fully resolved production quality is made.

Before any future rollout, review [the exact offline SQL](0015-review.sql), target,
roles, backup and lock impact; obtain separate hosted-migration/deployment
authorization. Apply 0015 before starting this application. The existing hosted
upgrade allowlist is intentionally unchanged; this document is not approval to
apply remote SQL. Legacy rows must never be backfilled as trusted. Do not run a
mixed old/new worker rollout that can continue stamping or replaying unfiltered
context.

Operational rollback: turn AI processing off using the existing `AI_ENABLED=false`
setting, keep schema 0015 and its stamps, and retain authenticated history
read/export. Use a forward repair before re-enabling AI. Do not downgrade/drop the
column or roll back to an unfiltered runtime: that reopens F03. An old binary also
rejects revision 0015 in readiness; returning to one requires an independently
reviewed readiness-compatible release with AI kept disabled. No rollback command
was executed in this task.

Next P0: establish an explicit per-turn evidence/capability contract and validate
numerical claims against current authorized tool results; retain the privacy
projection while defining F01 follow-up UX. Keep any optional reuse grant or
persistence migration in its own reviewed change.
