# Guest Experience Interface and Dependency Matrix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement the linked tasks. Steps use checkbox (`- [ ]`) syntax for tracking. This is a reference, not duplicate task ownership.

**Goal:** Connect every audit GE requirement to one producer, ordered consumers and executable verification.

**Architecture:** Shared interfaces have one canonical definition in their owning plan; matrix rows index them rather than invent variants.

**Tech Stack:** Same existing stack as [index](00-implementation-index.md).

**Spec:** All nine audit documents, especially [original GE roadmap](../05-implementation-roadmap.md).

## Global Constraints

Index constraints bind all rows. All new files/tables/tests/interfaces are proposed. No row is proof of implementation or test success. Explicit external gates do not prevent independent local work.

## Review Focus

1. New operation missing guest classification → GE-03.2 set-equality failure.
2. Contract field/name differs across UI/backend → GE-02.2/11.2 generated drift/typecheck.
3. Cleanup inventory omits new model/plain UUID reference → GE-06.1/10.3 coverage failure.
4. A task calls an unproduced helper → total-order/interface review below.
5. Pending SQL mistaken for approved artifact → GE-14.3 review refusal test.

## Total execution order (35 subtasks, 15 GE parents)

Use this total order even when plan files are grouped differently. GE-08 may optionally move after GE-03.2 for isolated public-only work, consuming only produced contracts and keeping CTA unavailable; the default below needs no parallel implementation.

| Order | Task / owner plan                                     | Prerequisites                   | Produced deliverable / consuming tasks                                                                  |
| ----- | ----------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1     | GE-00.1 / [01](01-foundation-and-guest-auth.md)       | none                            | Baseline/worktree/ledger → all                                                                          |
| 2     | GE-01.1 / [01](01-foundation-and-guest-auth.md)       | GE-00.1                         | Verified anonymous provider/error outcome → GE-02/04                                                    |
| 3     | GE-02.1 / [01](01-foundation-and-guest-auth.md)       | GE-01.1                         | 0016 core models/constraints/private grants → all guest backend                                         |
| 4     | GE-02.2 / [01](01-foundation-and-guest-auth.md)       | GE-02.1                         | Session/GuestInput/public readiness/flags → GE-03/04/08/09                                              |
| 5     | GE-03.1 / [01](01-foundation-and-guest-auth.md)       | GE-02.2                         | Lifetime/database time/SQL helper/registered predicate → GE-03.2/04/05                                  |
| 6     | GE-03.2 / [02](02-guest-expiry-and-permissions.md)    | GE-03.1                         | Requester/peer default denial, complete operation map → GE-04 onward                                    |
| 7     | GE-04.1 / [01](01-foundation-and-guest-auth.md)       | GE-03.1,GE-03.2                 | Owned intent/key binding + creation admission → GE-04.2/09.1                                            |
| 8     | GE-04.2 / [01](01-foundation-and-guest-auth.md)       | GE-04.1,GE-01.1                 | Atomic grant/recovery + cleanup/usage rows → GE-04.3/05/06/09                                           |
| 9     | GE-04.3 / [01](01-foundation-and-guest-auth.md)       | GE-04.2                         | End/logout permanent revocation → GE-05.4/09                                                            |
| 10    | GE-05.1 / [02](02-guest-expiry-and-permissions.md)    | GE-04.3                         | Transaction/deadline/output guard → GE-05.2–05.4/10                                                     |
| 11    | GE-05.2 / [02](02-guest-expiry-and-permissions.md)    | GE-05.1                         | AI/tool/SSE/store expiration → GE-05.3/06/07.3                                                          |
| 12    | GE-05.3 / [02](02-guest-expiry-and-permissions.md)    | GE-05.2                         | Memory/history/embed lifetime fence → GE-06/07.3                                                        |
| 13    | GE-05.4 / [02](02-guest-expiry-and-permissions.md)    | GE-05.3                         | Voice/export/deletion confirmation → GE-06/07.3/09                                                      |
| 14    | GE-06.1 / [03](03-guest-cleanup-and-cost-controls.md) | GE-05.4                         | Exhaustive purge + guarded mapped-provider delete → GE-06.2/07.2/10.3                                   |
| 15    | GE-06.2 / [03](03-guest-cleanup-and-cost-controls.md) | GE-06.1                         | Worker/reconciler/orphan helpers/metrics → GE-07/01.2/14                                                |
| 16    | GE-07.1 / [03](03-guest-cleanup-and-cost-controls.md) | GE-06.2                         | Shared counters/request/growth/concurrency → GE-07.2/10.2                                               |
| 17    | GE-07.2 / [03](03-guest-cleanup-and-cost-controls.md) | GE-07.1                         | Detached financial reservation/settlement, purge integration → GE-07.3                                  |
| 18    | GE-07.3 / [03](03-guest-cleanup-and-cost-controls.md) | GE-07.2,GE-05.2,GE-05.3,GE-05.4 | All paid adapters fenced, late settlement safe → guest UI/feedback/release                              |
| 19    | GE-01.2 / [01](01-foundation-and-guest-auth.md)       | GE-06.2,GE-07.3 + D04           | Hosted proof checkpoint → G1. If target absent, record BLOCKED hosted check and continue 20–35 locally. |
| 20    | GE-08.1 / [04](04-public-landing-and-guest-ui.md)     | GE-02.2                         | Callback/public boundary/session validator → GE-08.2/09                                                 |
| 21    | GE-08.2 / [04](04-public-landing-and-guest-ui.md)     | GE-08.1                         | Landing/readiness/cache/CSP → GE-09.1                                                                   |
| 22    | GE-09.1 / [04](04-public-landing-and-guest-ui.md)     | GE-07.3,GE-08.2                 | Explicit entry/stable public retry key → GE-09.2                                                        |
| 23    | GE-09.2 / [04](04-public-landing-and-guest-ui.md)     | GE-09.1                         | Guest status/expiry/abort epoch/copy → GE-12/13/14                                                      |
| 24    | GE-10.1 / [05](05-feedback-and-admin.md)              | GE-07.3                         | 0018 independent feedback/receipt/review schema → GE-10.2                                               |
| 25    | GE-10.2 / [05](05-feedback-and-admin.md)              | GE-10.1                         | Submission/state/idempotency/limits → GE-10.3/12.1                                                      |
| 26    | GE-10.3 / [05](05-feedback-and-admin.md)              | GE-10.2,GE-06.2                 | Feedback unlink/retention/redaction runbook → GE-11/14                                                  |
| 27    | GE-11.1 / [05](05-feedback-and-admin.md)              | GE-10.3                         | Independent live admin/reauth gate → GE-11.2                                                            |
| 28    | GE-11.2 / [05](05-feedback-and-admin.md)              | GE-11.1                         | Filter/list/summary/PATCH/generated DTOs → GE-12                                                        |
| 29    | GE-12.1 / [05](05-feedback-and-admin.md)              | GE-09.2,GE-11.2                 | Accessible voluntary form/guest fullstack → GE-12.2/14                                                  |
| 30    | GE-12.2 / [05](05-feedback-and-admin.md)              | GE-12.1                         | Protected escaped-text dashboard → GE-13.2/14                                                           |
| 31    | GE-13.1 / [06](06-interactive-onboarding.md)          | GE-09.2                         | Candidate compatibility gate or explicit deferred spotlight → GE-13.2                                   |
| 32    | GE-13.2 / [06](06-interactive-onboarding.md)          | GE-13.1,GE-12.2                 | Tour/inline guide/targets/cleanup → GE-14                                                               |
| 33    | GE-14.1 / [07](07-integration-testing-and-release.md) | GE-12.2,GE-13.2                 | Fullstack/matrix/regression/artifacts → GE-14.2                                                         |
| 34    | GE-14.2 / [07](07-integration-testing-and-release.md) | GE-14.1                         | 50 visitor/restart/restore proof → GE-14.3                                                              |
| 35    | GE-14.3 / [07](07-integration-testing-and-release.md) | GE-14.2; GE-01.2 for G1pass     | Pending release SQL/image/config/evidence/rollback; explicit release stop                               |

No circular implementation dependency: GE-06.1 initially purges only produced tables with paid flags off; GE-07.2 subsequently adds accounting settlement to the already-produced purge; GE-10.3 subsequently adds receipt unlink to it. GE-06.1 must not import nonexistent feedback/accounting modules or fabricate stub producers. Its initial coverage map grows when new models are produced. Final all-store proof occurs afterGE-10.3 andGE-14.

## Interface producer/consumer registry

Canonical signatures and exact DTO/schema fields live in their owner plans. References below are binding names, not optional suggestions.

| Interface                                                                                                  | Producer                             | Consumers                                        | Canonical definition                  |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------ | ------------------------------------- |
| ProviderSession.is_anonymous; anonymous_session; AnonymousSignupError.outcome                              | GE-01.1                              | GE-04.2,GE-01.2                                  | plan 01 GE-01.1                       |
| User account_kind/guest_started_at/guest_expires_at; immutable/session cap triggers                        | GE-02.1                              | security/cleanup/quota/UI                        | plan 01 foundation schema             |
| GuestProvisioningAttempt/CleanupJob/Usage/AbuseBucket/BudgetDay/CostReservation/OperationLink              | GE-02.1                              | GE-04/06/07                                      | plan 01 foundation schema             |
| GuestInput/GuestQuota/SessionView/features.feedback/public experience flags                                | GE-02.2                              | all frontend/provisioning                        | plan 01 HTTP/DTO table                |
| database_time/lifetime_allows/assert_guest_active/require_registered_user                                  | GE-03.1                              | requester/peer/deadline/workers                  | plan 01 GE-03.1                       |
| is_provider_session_active(app_session_id,app_user_id)                                                     | GE-03.1                              | existing verify_session and workers with actor   | plan 01 GE-03.1; no arbitrary subject |
| require_registered_actor and both-kind social predicates                                                   | GE-03.2                              | social/activities/moderation/staff/background    | plan 02 inventory                     |
| create_guest_intent/claim_guest_attempt                                                                    | GE-04.1                              | create_guest, guest UI                           | plan 01 GE-04.1                       |
| create_guest/grant_guest/recover_guest_credentials/end_guest                                               | GE-04.2/04.3                         | routes/logout/UI/guest account deletion          | plan 01 GE-04                         |
| GuestDeadline/guest_deadline/final_guest_authorization/guard_guest_dispatch/GuestOutputMiddleware          | GE-05.1                              | all private HTTP/AI/tools/voice/embed/export     | plan 02 deadline contract             |
| AiRuntime.expire_guest / capped store/events                                                               | GE-05.2                              | cleanup/end/worker                               | plan 02 GE-05.2                       |
| embedding._authorization + capped proposal/history/index                                                   | GE-05.3                              | background/retrieval/cleanup                     | plan 02 GE-05.3                       |
| guestConfirmation on ExportInput/DeletionInput                                                             | GE-05.4                              | Privacy/guest export/end UI                      | plan 02 GE-05.4                       |
| purge_guest/delete_guest_provider_identity                                                                 | GE-06.1                              | process_guest_cleanup, cost/feedback integration | plan 03 inventory/helper contract     |
| process_guest_cleanup/reconcile_guest_provisioning/find_guest_orphan_subjects/delete_orphan_guest_identity | GE-06.2                              | lifespan/startup/hosted probes                   | plan 03 helper/worker contract        |
| reserve_guest_creation/canonical_client_key; reserve_guest_quota/guest_quota_view                          | GE-04.1 creation, GE-07.1 extensions | paid adapters/SessionView/feedback               | plan 01 GE-04.1; plan 03 quotas       |
| Reservation/reserve_guest_operation/settle_guest_operation/mark_guest_dispatched                           | GE-07.2                              | GE-07.3 runtime/voice/embed/purge                | plan 03 financial algorithm           |
| guest-aware Model adapter with before_dispatch                                                             | GE-07.3                              | SdkProvider; no registered behavior change       | plan 03 GE-07.3                       |
| readAuthCallback/classifyEntry/validateSession/AppEntry/RealApp props                                      | GE-08.1                              | public/guest entry                               | plan 04 component table               |
| explicit idempotencyKey/guestIntent ApiClient options; beginOrResumeGuest                                  | GE-09.1                              | GuestEntry only public creation                  | plan 04 GE-09.1                       |
| useGuestLifecycle/API unauthorized error/abort epoch                                                       | GE-09.2                              | private tree/feedback/tour/audio/streams         | plan 04 GE-09.2                       |
| AppFeedback/FeedbackSubmissionReceipt/FeedbackReviewEvent and schemas                                      | GE-10.1                              | services/admin/retention/UI                      | plan 05 canonical schema              |
| submit_feedback/purge_feedback                                                                             | GE-10.2/10.3                         | routes/worker/cleanup                            | plan 05 API/service/retention         |
| require_staff(feature='feedback')/assert_feedback_admin                                                    | GE-11.1                              | admin queries/status                             | plan 05 staff contract                |
| list_feedback/summarize_feedback/review_feedback + filter/cursor/DTO                                       | GE-11.2                              | FeedbackAdmin                                    | plan 05 API/filter contract           |
| FeedbackPage/FeedbackAdmin                                                                                 | GE-12.1/12.2                         | Shell/settings/footer routes                     | plan 05 UI tasks                      |
| TourStep/TourState/TourAdapter/waitForTourTarget/TourActivity/TourController                               | GE-13.1/13.2                         | settings/guide/activity/lifecycle                | plan 06 state/target table            |

## New API inventory and task ownership

| API (/api/v 1 prefix)                                                        | Producer     | Security/tests                                                                              |
| ---------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------- |
| GET /public/experience                                                       | GE-02.2      | Public/no identity/no-store; test_guest_contracts + landing                                 |
| POST /auth/guest-intents                                                     | GE-04.1      | ExactOrigin/customheader/HttpOnlyintent/shared admission; test_guest_provisioning           |
| POST /auth/guest                                                             | GE-04.2      | Intent+stablekey+CAPTCHA+age+provider verification; test_guest_auth/provisioning/provider   |
| POST /auth/guest/end                                                         | GE-04.3      | Guest+CSRF/identity revocation; test_guest_auth                                             |
| GET /session expanded                                                        | GE-02.2/03.1 | Guestdeadline/no sliding; test_guest_contracts/expiration                                   |
| Existing private/SSE/voice/export routes                                     | GE-05        | Final lifetime/purpose/owner/output; test_guest_inflight/embeddings/exports                 |
| Existing social/staff routes                                                 | GE-03.2      | Requester+peerregistered; test_guest_permissions                                            |
| POST /feedback; GET /feedback/submission-state                               | GE-10.2      | Eligible liveactor+CSRF/receipt/sharedlimits; test_feedback/privacy                         |
| GET /admin/feedback; GET /admin/feedback/summary; PATCH /admin/feedback/{id} | GE-11.1/11.2 | Permanent live admin+12hreauth/independent flag; PATCHCSRF/version/key; test_feedback_admin |

No guest conversion endpoint, unauthenticated public feedback POST, post-expiry feedback token, public feedback lookup, solo structured activity API or client database route is introduced.

## Shared file/migration ownership sequencing

| Existing shared file group                                    | Permitted sequential owners / responsibilities                                                                                       |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| backend/app/core/security.py                                  | GE-03.1 lifetime →03.2 registered dependency →05.1 final transaction/output context; signatures preserved                            |
| backend/app/modules/auth/{provider,routes}.py                 | 01.1 verification →02.2 session DTO →04.2 cookie/grant/permanent-path rejection →04.3 logout                                         |
| backend/app/main.py                                           | 02.2 readiness/DTO route →04.1 guest router →05.1 middleware →06.2 isolated workers →08.2 CSP →10.2 feedbackrouter →11.1 adminrouter |
| core/config.py, .env.example, deploy/runtime.env.example      | 02.2 flags/fields →07 quota/pricing validation →14.3 documented release package; no secret values                                    |
| database/models.py, guests/models.py                          | 02.1 schema only; later service tasks consume; new schema delta needs explicit migration                                             |
| 0016_guest_foundation /0017_guest_security /0018_app_feedback | 02.1 /03.1+04.2+06 helpers while unshipped /10.1; next free revision on rebase; pending reviewed SQL14.3                             |
| conftest.py, tests/e 2e_server.py, LocalAuth                  | 01.1 flags/provider fixtures →02.1 metadata/trigger →06 helper/childfixtures →10 feedback metadata →14 full HTTP journey             |
| AI runtime/provider/store/persistence/memory/embeddings       | 05 deadlines →07 quota/financial dispatch; preserve validated output/source/version semantics                                        |
| users/lifecycle.py, guests/lifecycle.py, jobs/retention.py    | 06 exhaustive purge →07 detached liability →10 receipt/feedback retention                                                            |
| frontend main/Auth/RealApp                                    | 08.1 public/callback →09 guestcontexts/copy →12 feedbackroutes →13 target/blocker attributes; no broad rewrite                       |
| api/client.ts, stream.ts                                      | 09 explicit public key/unauthorized error/abort epoch; registered defaults and REAUTH_REQUIRED preserved                             |
| OpenAPI/generated TS/API/config/schema docs                   | 02.2 →05.4 →10.2 →11.2 regenerations after producing backend changes;14 finaldrift                                                   |
| deploy/Caddyfile and backend CSP                              | 08.2 shared cache/header/CAPTCHA proof;13 tourcompat;14 packaging                                                                    |
| approved reviewed-sql/*.sql and MANIFEST.json                 | No automatic edits/reapproval.14.3 creates separate pending artifact outside directory; explicit ownerreview later                   |

## Requirement traceability

Audit section IDs below refer to the unchanged original documents. All test files under backend/tests unless frontend path named. Main requirements may map to several focused subtasks.

| Requirement/source                                                                                                 | Implementing tasks            | Acceptance test/evidence                                                             |
| ------------------------------------------------------------------------------------------------------------------ | ----------------------------- | ------------------------------------------------------------------------------------ |
| Baseline/unchanged registered architecture, audit 00/01/06                                                         | 00.1,14.1–14.3                | Fullbaseline/static/type/contracts/build/registered suites; freshcounts              |
| Independent anonymous identity, verified claims/BFF/cookies/CSRF,02§2/3                                            | 01.1,02.1–02.2,04.1–04.2      | test_guest_provider/auth/provisioning                                                |
| Age 16+, registered 18+, explicit consent,02§1/6                                                                   | 03.1–03.2,04.2,09.1           | test_eligibility + guest under 16/consent/permissions                                |
| Absolute 7200, no sliding/refresh/restart/tabs,02§4                                                                | 03.1,05.1,09.2                | mandatory 1–3; SQLhelper; guest-journey/expiry                                       |
| Provisioning ambiguous/localfailure/lostresponse/orphan/retries,02§2                                               | 04.1–04.2,06.2                | mandatory 8–10, marker/fence/lookup/lease negativecases                              |
| Fivebots/personal journal/history/approvedmemory,02§6                                                              | 05.2–05.4,07.1,09.2           | synthetic 5bot journey/memory/mood/history caps; permission matrix                   |
| No matching/discovery/profile publishing/requests/messages/shared activities/reveals/notifications/staff,01§4/02§6 | 03.2,06.1,09.2                | mandatory 4–7; full operation map; peerlegacy/canaries/no polling                    |
| SSE/tool/HTTP/voice/export/embedding deadline races,02§4                                                           | 05.1–05.4,07.3                | mandatory 11–12/23; fakeprovider/barriers/finaldispatch order                        |
| Exhaustive deletion/metadata/provider/noresurrection,01§5/02§5                                                     | 06.1–06.2,07.2–07.3,10.3,14.2 | inventory/metadata set/canaries; mandatory 13–17; restore test                       |
| Durable quotas and cost after purge,02§7                                                                           | 04.1,07.1–07.3                | 25turn/6 minute/1 active/10 global; voice 6/180s/2 minute/1/3; uncertain budget/race |
| Public root/hash/callback/registered restoration,03§1                                                              | 08.1–08.2                     | mandatory 18–20; auth/landing/deeplink tests                                         |
| Vietnamese brand/demos/5assistants/privacy/mobile/SEO/cache/CSP,03§2/3/6                                           | 08.2,09.2,14.1                | approvedcopy, initialHTML/headers/chunks,320–1440/200%/axe/manual                    |
| Trial disclosure/age/CTA/timer/expired/newtrial/register/lockedcopy/allstates,02§8/03§7                            | 09.1–09.2                     | guest.spec/guest-expiry/guest-journey exact state matrix                             |
| Feedbackrating 1–5/optional categories/comment≤1000/ratingonly,04§1/3/4                                            | 10.1–10.2,12.1                | strictbody/DB validation; ratingonly mobilekeyboard                                  |
| Separate feedback/no identity/noattachments/idempotency/abuse/retention,04§3–5                                     | 10.1–10.3,07.1,12.1           | mandatory 16/23; schema/FK/payload/runtime privileges/180d tests                     |
| Adminrole/reauth/flags/status/aggregates/spam/zero,04§6                                                            | 11.1–11.2,12.2                | mandatory 22; filter/cohort/status race/escaped text                                 |
| Optionaltour/candidate/StrictMode/CSP/GSAP/a 11y/readiness 3s/replay/cleanup,03§4–6                                | 13.1–13.2                     | mandatory 21; compatibility matrix/manualSR/expiry/blockers                          |
| Featureoff/rollback/restore never resurrect,06§9                                                                   | 06.2,07.3,14.2–14.3           | mandatory 24–25; entry-off worker tests/compatible image                             |
| D01 deletion/privacy/SLO/counter exceptions                                                                        | 06,08.2,09.2,14.3             | local implementation proceeds; publicguestG3hold                                     |
| D02 numerical paid budget                                                                                          | 07.2–07.3,14.3                | unset fails closed; approvednumberneededG4                                           |
| D03 proposed 180dfeedbackpolicy                                                                                    | 10,12.1,14.3                  | tests proposed policy; publiccollectionG3/G5hold                                     |
| D04 approved hosted target                                                                                         | 01.2,14.3                     | guard refuses unapproved target; hostedG1hold                                        |

## Completeness/consistency review checklist

- [x]35 unique numbered tasks,15 GE parents, one owner per subtask; dependencies produced in totalorder (external 01.2 separately gated).
- [x] All 25 mandatory scenarios have exact commands/oracles and named owner/test file.
- [x] All 100 existing operations classified; newly produced APIs added as exact tuples; no prefix-only authorization.
- [x] Every 38 baseline ORM table plus new guest/feedback tables classified; FK/plainUUID/RAM/external boundaries included.
- [x] Field/endpoint/error/flag names match canonical plans; no approved budget/retention falsely asserted.
- [x] Only produced modules imported; phased purge extensions avoid future-placeholder dependencies.
- [x] Required local skills/version-aware Sonnet execution and permission boundaries included in final prompt.
- [x] Relative links/sourcepaths/fences/command conventions validated; no original audit/appcode/.gitignore modification.

This planning checklist is self-review for document quality; implementation checkboxes remain unexecuted until Sonnet produces evidence.
