# 12 — Release Readiness

Status today: **HOLD** — the current codebase is a strong single-user/two-fixture MVP, but Pillar B lacks activities, informed request consent, moderation and durable connections (see [01 §3](01-codebase-audit.md#3-confirmed-defects-and-product-gaps)); staging infrastructure does not exist.

## 1. Release trains

| Release | Contents | Migration | Default flags |
|---|---|---|---|
| R1 | Phase A (cleanup) + Phase B (stabilization) + I-05 (AI quota) + I-06 (PII advisory) | 0011 | — |
| R2 | Phase C (matching v2, shadow first) | 0012 | `MATCHING_SCORER=shadow` → `v2` after gate |
| R3 | Phases D–H (activities + UX) | 0013 | `ACTIVITIES_ENABLED=true` on staging first; `ACTIVITY_KINDS` staged icebreaker → quiz → focus |
| R4 | Phase I (moderation, enforcement, privacy, ops) + Phase J qualification | 0014 | `MODERATION_ADMIN_ENABLED=true` |
| Beta launch | R1–R4 on production with go/no-go below | — | — |

R1–R3 may ship to staging independently; **real-user beta requires R4** (moderation is a launch blocker for a social product).

## 2. Go/no-go gates (all must be PASS with evidence links)

| Gate | Evidence |
|---|---|
| G1 Backend green | ruff, mypy, pytest (count ≥ baseline 278 + new) |
| G2 Frontend green | typecheck, vitest, build, mocked E2E |
| G3 Full stack | all `tests/fullstack/*` incl. activities, matching v2, responsive/a11y |
| G4 Contracts | OpenAPI/TS drift check clean |
| G5 Migrations | 0011–0014 rehearsed on restored snapshot; applied with approval; advisors clean (only accepted WARNs) |
| G6 Matching | offline gate report (T-EVAL-01); shadow overlap logged ≥ 3 days on staging |
| G7 Safety | moderation runbook approved; at least one named moderator with staff role; report → resolve exercised on staging |
| G8 Privacy | privacy notice approved by owner/legal; provider retention settings confirmed (Q-02) |
| G9 Cost | `AI_DAILY_TURNS_PER_USER` and `AI_DAILY_BUDGET_USD` set; accounting enabled; budget alarm wired |
| G10 Ops | staging deploy + rollback rehearsal; restore drill; alarms configured; on-call contact named |
| G11 Performance | 50-user load report meets PR-O-03 on the staging host |
| G12 Email | signup confirmation and password recovery delivered via configured SMTP (Q-05) |

## 3. Known non-blocking limitations for beta

- Single worker/replica (documented capacity envelope).
- No push/email notifications for new messages (badges only).
- Self-declared age.
- No in-app unblock/appeal (email support).
- English practice and semantic profile matching are post-MVP.

## 4. Launch-day checklist

1. Confirm backup taken ≤ 24 h before.
2. Confirm flags per release table; `AI_LOCAL_TEST_USER_IDS=[]`.
3. Health `/api/v1/health/ready` = 200 on the new image.
4. Smoke: login, AI turn, publish, discover, request/accept, message, icebreaker between two staff test accounts (synthetic, deleted afterwards).
5. Watch alarms for 2 h; moderator on call for the first week.

## 5. Rollback triggers

5xx > 2 % for 10 min; readiness failing; any cross-user data exposure (immediate rollback + incident); AI spend > ceiling alarms repeatedly; activity integrity failures (duplicate sessions, leaked answers) → disable `ACTIVITIES_ENABLED`.
