# Full-stack evidence (H-04, J-01)

Harness: `scripts/test_fullstack.py` — real FastAPI + local PostgreSQL (`prod_e2e_test`, recreated per run) + Vite, Playwright Chromium, synthetic users only. Server flags (test env): `ACTIVITIES_ENABLED`, `MODERATION_ADMIN_ENABLED`, `FOCUS_TEST_PLAN_SECONDS=20`, `MATCHING_SCORER` from `E2E_MATCHING_SCORER` (default `v1`, the production default). Date: 2026-10-25.

## Final run (default scorer v1)

**21 passed, 0 failed, exit 0, 5.5 min.** Tracked historical screenshots (`docs/mvp-validation/screens`, `docs/plans/validation-artifacts/visual`) were restored afterwards; the new layout is captured in [`../screens/`](../screens/).

| Spec | Tests | Covers |
|---|---|---|
| `activities.spec.ts` (new) | 4 | T-ICE-02 (two browsers, 3 rounds, peer answer absent from screen **and** API until both answered, private feedback, inline history card); T-ACT-03 (stream drop + reload resumes round 2); T-QUIZ-02 (5 rounds, `correctIndex` absent from the open round, equal team score); T-FOCUS-02 (one-cycle server-timed session to completion); block mid-activity closes the peer's dock and room |
| `matching-v2.spec.ts` (new) | 2 | Six real profiles: identical twin first with "Nhiều điểm chung", ≤ 3 reasons per card, no percentages, strict-goal and no-shared-language peers excluded, goal rule per scorer; v2-only goal case (see below) |
| `moderation.spec.ts` (new) | 1 | Report with selected message → staff queue (opaque refs, no ids/emails) → claim → restrict 7 days → subject gets 403 `SOCIAL_RESTRICTED`, restricted notice, room closed, absent from discovery; non-staff 403 `STAFF_REQUIRED` |
| `responsive.spec.ts` (new, H-04) | 1 | Discovery, Messages, chat with live activity dock, admin queue at 390×844, 430×932, 768×1024, 1280×900, 1440×960 + collapsed dock at 390×480: axe `wcag2a/wcag2aa/wcag21aa` 0 violations, no horizontal overflow, composer in viewport |
| `chat-history`, `journeys`, `mvp` (existing, T-REG-01) | 13 | Unchanged journeys; selectors moved to the Discovery tabs where requests now live |

Under `E2E_MATCHING_SCORER=v2`: `matching-v2.spec.ts` **2 passed** (including the v2-only goal case).

## Defects found by these runs and fixed

| Defect | Fix | Regression test |
|---|---|---|
| SSE stream folded an activity change that landed between the client's first fetch and the stream's first poll into its baseline; the invitee never saw the invitation while the stream stayed healthy (no polling) | Stream announces activity state on connect, like messages | `test_stream_resyncs_activity_on_connect` (RED → GREEN) |
| Moderator acting right after "Nhận xử lý" sent the pre-claim version → false `REPORT_CHANGED` | Claim response replaces the row immediately | full-stack `moderation.spec.ts` |
| Restricted user's discovery returned generic `MATCH_UNAVAILABLE` | `SOCIAL_RESTRICTED` with the reason | `test_enforcement.py` (RED → GREEN) |
| API-connected test pairs shared one profile; partners fell out of the 5-card list as pairs accumulated | Unique v1 interest triple per pair (test helper) | all pair-based specs |

## Open defect (P1, product decision)

`/taxonomy` always offers the v2 vocabulary, but the default `MATCHING_SCORER=v1` scores v2-only goals (`study-buddy`, `language-practice`) and v2-only tags as invalid, so such users silently get **no suggestions**. Marked `test.fail` under v1 in `matching-v2.spec.ts` (flips when fixed); passes under v2. Options: serve v2, restrict the editor to the v1 vocabulary while v1 is served, or extend v1.

## Not run here

`tests/supabase/journey.spec.ts` (hosted, writes data — needs approval); selectors updated for the tabs only.
