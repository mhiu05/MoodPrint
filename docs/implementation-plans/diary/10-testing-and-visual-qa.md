# Testing and visual QA

Current verification: **PARTIAL until final backend follow-up and PR finishing are recorded**. The [ledger](14-implementation-progress.md) distinguishes passing browser/Storage/component checks from whole-suite failures and post-fix reruns. Do not read the planning NOT_STARTED labels below as final evidence.

Status: NOT_STARTED. Every PASS below requires a recorded command and result in14. Synthetic data only. Local PostgreSQL database names must end `_test`; never use backend/.env database as test target.

| Layer | Required behavior / command |
| --- | --- |
| Backend journal | pytest owner CRUD, two/day, drafts, dates, filters/pagination, stale writes and idempotency; route authorization matrix and guest expiry. |
| Storage | Fake httpx adapter tests MIME/size/immutable paths/completion verification/sign expiry, failure/retry/outbox cleanup and cross-owner denial. Hosted bucket remains unverified. |
| Lifecycle | Export/deletion/account/retention/guest inventory, no signed links in exports, outbox survives account erasure. |
| AI | Nhịp-only search, bounded owner evidence and citations, invalid IDs, data-version/privacy fences; existing scoped mood and context tests. |
| Migration | Fresh Alembic upgrade/current/check on separate disposable DB, RLS/grants/indexes and non-destructive old Mood rows. |
| Frontend unit | `npm.cmd test`; date/calendar/filter/upload utility and safe citation cases. |
| Contracts | `python scripts/export_openapi.py`; `npm.cmd run contracts:generate`; typecheck and contract drift review. |
| Build | `npm.cmd run typecheck`, `npm.cmd run build`. |
| Browser | Playwright real editor/save/reload/edit/delete, drafts, calendar/timeline/search, media uploads/playback, upload/mic/network errors, version conflict, dirty navigation. |
| Accessibility | axe plus keyboard focus/labels/native controls/status; reduced motion and long content. |
| Responsive / visual |360,390,430,768,1024,1440; no document overflow, bottom nav overlap, clipped chips/media; capture six experiences. |
| Regressions | Full backend suite (skips reported), frontend unit suite and relevant existing E2E; don't rewrite legitimate assertions to hide regressions. |

Browser fixture data proves UI interaction, not real hosted Auth/Storage/OpenAI. Use real HTTP/DB API tests for ownership and receipt behavior. Browser recording uses synthetic MediaRecorder input where supported; separately test permission denial and file fallback. Do not claim physical microphone/browser-device compatibility from a stub.

Keep screenshots under `docs/implementation-plans/diary/evidence/` or a clearly linked artifact path; inspect each capture. Compare layout/hierarchy to references and document deliberate changes. Visual regression baseline captures are evidence of this branch, not proof of long-term stability until reviewed. Fullstack/network hosted checks are separate release gates.
