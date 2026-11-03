# Live release verification — 03/11/2026

Status: IN PROGRESS. This document supersedes offline-only evidence only for checks
explicitly recorded here. No production success is implied by local test results.

User authorized completing deployment and live verification on
`https://moodprint.duckdns.org`, and approved an Apify ceiling of **USD 0.50 per run**.
Keep five places, sixty actor seconds, five operations per user/day, and a shared
Search budget of USD 5/day within the existing global USD 20/day budget.

## Observed production starting state

- EC2 `i-0664d6ea5930452db`, AWS account `231266553536`, region `ap-southeast-2`.
- API/web/proactive healthy at revision `d83c01f4388422d5a7f9582762cb54a90624ef3b`.
- Hosted database project `roznanxbiyqybjpvtilq`, schema `moodprint`, revision
  `0024_three_agent_groups`. Search tables absent.
- Backend login inherits `moodprint_app` and `moodprint_runtime`; existing receipt
  tables have runtime DML grants. No role expansion needed.
- Runtime has OpenAI credential, lacks Apify credential and Search/defaults flags.
- Installed Compose/deploy script have no Maps service/health gate.
- Stored sharing inventory: three rows (two false, one true). Existing check-in
  settings: one account, two schedules. Preserve rows and schedule values.
- GitHub exact-main verification/publication for the starting revision succeeded.

## Provider verification and rulings

- Live Apify metadata: successful build `0.14.782`, build ID
  `iGk3vkI1QM1iLooFy`, current pricing started `2026-06-30T13:23:33.247Z`, minimum
  accepted maximum charge **USD 0.50**. This is a spending ceiling, not a flat bill.
- Ruling: replace the planned USD 0.05 cap with the user-approved USD 0.50 cap in
  both provider request and financial reservation. Retain no-enrichment input.
- First Web probe reached the twelve-second deadline. A regression requires low
  reasoning effort; the subsequent real request completed in 6.23 seconds,
  one hosted call, 8,691 input tokens, 128 output tokens, one python.org citation.
  Existing twelve-second timeout, one-call cap and 1,200 output-token cap remain.
- Official OpenAI pricing checked: USD 0.01 per Web tool call plus input/output
  tokens. The existing conservative token reservation remains in force.
- One real Apify run completed with five places; all had name/category/address/
  rating/Google Maps URL, four had opening hours. Final billed amount USD 0.0202.
  Dataset, KV store, request queue and run metadata were deleted successfully.
- A missing-area follow-up now accepts an exact public city, optionally with a
  numbered district, on the immediate next turn. Only the canonical query label
  is retained in RAM for five minutes, scoped to user/session/thread/data version/
  agent. Logout, failed question and unrelated replies clear that continuation.
  This neither persists location nor makes prompt-menu selections sticky.

## Remaining execution checklist

- [x] Finish targeted real-PostgreSQL regressions and frontend checks.
- [x] Generate/review exact additive SQL 0024→0028; rehearse on disposable DB.
- [x] Verify one bounded live Apify run, final billing and storage cleanup.
- [ ] Publish reviewed source through exact-main CI and attested image pipeline.
- [ ] Preserve previous runtime/image pair, apply bounded migration, install Maps
  deployment assets, update existing SecureString without exposing secret values.
- [ ] Recreate API/proactive/Maps with verified configuration and check readiness.
- [ ] Verify real authenticated Web citations/reload, Maps completion/cancel/reuse,
  skills one-shot behavior, effective defaults and per-agent schedule persistence.
- [ ] Record final revision, evidence, costs, limitations and rollback procedure.

The local scratch evidence directory is `.tmp/search-release-live/`. It may contain
authentication state and is never part of the release artifact. `.gitignore` is
unchanged. CAPTCHA remains enabled; authenticated browser verification awaits the
user completing login in the dedicated Chrome tab.

## Fresh pre-publication verification

- Backend: 230 targeted tests passed against owned disposable PostgreSQL (271.64s),
  including actual chat admission/rehydration for Maps area follow-up, financial
  reservation and failed-origin cleanup. Ruff clean; Mypy 184 source files clean.
- Frontend: 241 unit tests plus two Node regressions passed; production build passed.
  Final six-spec browser suite: 66 passed (2.3min). Earlier broader suite was
  interrupted before printing a final result, so is not reported as a pass.
- Deployment: 31 unittest cases passed in Linux with Docker Compose available.
  Windows lacks `fcntl`; the first slim Linux runner lacked Docker CLI. Both were
  test-environment limitations, not successful runs.
- Documentation inventory, OpenAPI export and generated TypeScript contracts checked.
- Exact SQL SHA256: `273d39d69b63c9bccc2178e010ff6e6479e6de30b653be95d517777026ccf48f`,
  6,568 bytes. Independent review found no P0/P1; exact artifact rehearsal plus
  `alembic check` passed. No hosted DDL executed at this checkpoint.
- Automatic release polling paused for controlled migration/deployment. Existing
  application services continue serving the starting revision.

Pre-existing edits in the five auth/landing files remain uncommitted and are
excluded from this Search release. The accessible login regression accepts both
supported heading variants; no `.gitignore`, credential or generated screenshot
is included in the release commit.
