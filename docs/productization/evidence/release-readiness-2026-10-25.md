# Release readiness — 2026-10-25

Audience: the product owner deciding whether to start the private beta.
Branch `docs/productization-plan` (not merged; `main` untouched). Gates from [12 §2](../12-release-readiness.md#2-gono-go-gates-all-must-be-pass-with-evidence-links).

**Decision: HOLD.** The code is implemented and verified locally (backend, frontend, full stack with two browsers), but every gate that needs staging, the hosted database, an owner decision or legal review is still open, one product defect (P1, matching vocabulary) needs a decision, and local load latency misses the target.

| Gate | Status | Evidence | Owner / next step |
|---|---|---|---|
| G1 | PASS | Backend: ruff clean, mypy clean (85 files), pytest **473** passed on local PostgreSQL (baseline 278) | — |
| G2 | PASS | Frontend: typecheck 0, vitest 47 passed, build OK, mocked Playwright 59 passed | — |
| G3 | PASS (local) | Full stack 21 passed incl. activities, matching, moderation, responsive/axe; v2 mode 2 passed — [fullstack.md](fullstack.md) | Repeat on staging (J-04) |
| G4 | PASS | `backend/openapi.json` and `frontend/src/api/generated/schema.d.ts` regenerated with the code; typecheck consumes the generated types | — |
| G5 | BLOCKED | Review SQL 0011–0014 byte-match fresh exports and execute verbatim locally — [migrations/README.md](../migrations/README.md) | Operator: hosted dump → snapshot rehearsal → approval → apply → advisors |
| G6 | FAIL | Offline gate met only on provisional proxy labels; scorer stays v1 — [matching-gate.md](matching-gate.md). Open P1: v1 returns no suggestions for v2-only goals/tags ([fullstack.md](fullstack.md#open-defect-p1-product-decision)) | Owner: choose v2 / restrict editor / extend v1; human-labelled set; shadow logs ≥ 3 days on staging |
| G7 | BLOCKED | Runbook [moderation.md](../runbooks/moderation.md); queue/claim/resolve exercised locally (full stack) | Owner: approve runbook, fill Q-03 contacts, name a moderator, exercise on staging |
| G8 | BLOCKED | Draft [privacy-notice-draft.md](../privacy-notice-draft.md) | Owner + legal sign-off; Q-02 provider retention/region |
| G9 | BLOCKED | Quota and budget guard implemented and tested (`test_ai_quota.py`); alarm config `deploy/aws/cloudwatch-alarms.json` | Operator: set `AI_DAILY_TURNS_PER_USER`, `AI_DAILY_BUDGET_USD`, `AI_ACCOUNTING_ENABLED=true` on staging; create the alarm (approval) |
| G10 | BLOCKED | Local restore drill PASS — [restore-drill.md](restore-drill.md); runbooks [backup-restore.md](../runbooks/backup-restore.md), [incident.md](../runbooks/incident.md) | Operator: staging deploy + rollback rehearsal (J-04), hosted-dump drill, alarms in AWS, on-call contact |
| G11 | FAIL (local) | 50 users: functionally clean, latency over target on the laptop host — [load-50.json](load-50.json) | Re-run on the staging host; investigate candidates/session p95 if still over |
| G12 | BLOCKED | — | Q-05 SMTP for signup confirmation and recovery |

Readiness level reached: **FULLSTACK_VERIFIED** (code implemented, local tests and two-browser full stack green). Not STAGING_VERIFIED, PRIVATE_BETA_READY or PUBLIC_MVP_READY.
