# Self-contained implementation prompt for Claude Code

Copy the following prompt into a future implementation session. **Do not execute it as part of this audit.**

---

You are implementing three related MoodPrint features: a two-hour temporary guest trial using Supabase Anonymous Auth, a public Vietnamese landing page with optional/replayable spotlight onboarding, and minimal app ratings/feedback with a protected admin dashboard. Preserve existing registered-user AI, privacy, matching, messaging, activities and moderation behavior.

Repository: `https://github.com/mhiu05/MoodPrint`, local workspace normally `E:\MoodPrint`. Audit baseline was `main` commit `984753389aa8bd4b3112b19a8beceb1e538fd659` on2026-10-28 Asia/Bangkok. Inspect latest main and current work before modifying anything; line references may have moved. Do not assume the live site runs this SHA. Supabase Anonymous Sign-ins have been enabled according to the owner, but this does not implement guests in the app.

Read these exact planning documents, in order:

1. `docs/guest-experience/00-feasibility-summary.md`
2. `docs/guest-experience/01-current-architecture-audit.md`
3. `docs/guest-experience/02-guest-auth-design.md`
4. `docs/guest-experience/03-landing-onboarding-design.md`
5. `docs/guest-experience/04-feedback-system-design.md`
6. `docs/guest-experience/05-implementation-roadmap.md`
7. `docs/guest-experience/06-testing-and-release-plan.md`
8. `docs/guest-experience/07-risks-and-open-decisions.md`

Read root and closest nested `AGENTS.md`, `CLAUDE.md`, README, architecture, manifests, existing tests and applicable local skills. Follow project workflow: understand → baseline → plan → test-first implementation → verify → report. Use skill guidance without letting it override the owner's scope/security rules. Use parallel agents only when explicitly authorized by applicable instructions. Do not change `.gitignore` unless the owner specifically requests it.

First inspect `git status --short`, branch and remote main. Preserve all user work. Create a **separate feature branch**, proposed `feature/guest-experience`, from the reviewed main or a suitable isolated worktree. Do not reset/clean/discard changes, force push, merge to main or deploy. Do not copy secrets, production sessions or real private records into fixtures/artifacts. No production database resets, hosted migrations, Auth Dashboard changes, infrastructure changes or paid model load/evals are authorized by this prompt alone. A concrete reviewed release package and explicit owner release decision are required for those actions.

Current architecture facts to verify before building:

- Python3.12 FastAPI/SQLAlchemy/psycopg/Alembic with private `moodprint` PostgreSQL schema; OpenAI Agents SDK; React19/TypeScript/Vite/HashRouter/CSS/GSAP. No Redis or tour library installed at audit time.
- Existing BFF verifies Supabase provider users and issues opaque HttpOnly MoodPrint cookies; CSRF, versioning and ownership are server-enforced. Provider tokens are not the normal browser app session. Existing app sessions slide by activity; guest sessions must not.
- Five assistant IDs: `may`, `guong`, `nhip`, `rure`, `caunoi`. Saved history is opt-in; approved memory is explicit; Voyage semantic indexing is separate opt-in. Existing voice is bounded WAV transcription preview, not a realtime voice agent.
- Personal use requires existing self-declared16+ eligibility and explicit relevant consent. Social requires18+ and published/consented registered users. Current social checks have no guest kind; you must add backend denial across all routes and peer-selection/service gates.
- Existing account deletion leaves a tombstone and some metadata; implement exhaustive guest hard purge and provider cleanup, not just a call to existing account deletion. Same-identity conversion/data migration is deferred.
- Supported MVP topology is one backend worker/replica. Existing AI admission has shared PostgreSQL coordination, while raw temporary context, some rate counters and stream slots are in process. Do not change worker count to claim scale.
- Public root is currently session-gated; preserve existing `/#/...` links and real `/auth/callback` token sanitization. Keep MoodPrint's current forest-green/off-white identity, tokens, avatars and accessible primitives.
- Existing shared-activity rating is unrelated to overall app1–5 feedback. Existing staff roles/reauth can be reused, but guest/normal users must never access feedback administration.

Implement in exact phase/dependency order from roadmap task IDs:

1. **GE-00/01:** establish baseline and reproduce documented capacity outcomes; prove anonymous claim/body/CAPTCHA/creation compensation contracts with synthetic tests. Hosted synthetic Auth creation/deletion needs a separately approved non-production target. Never use the connected production project for destructive testing.
2. **GE-02/03:** compatible schema and SessionView expansion; immutable server account kind/start/deadline; absolute lifetime/security helper; deny guest social/staff access, including reads, underlying peer gates and forged legacy rows. Keep all old registered rows registered.
3. **GE-04:** idempotent creation intent, server-side anonymous provider sign-in, same cookie/CSRF protection, age declaration and disabled consents, lost-response recovery, orphan reconciliation and explicit guest end/logout.
4. **GE-05/06/07:** per-content/tool/provider/finalization expiry fences for SSE/AI/voice/memory/jobs/exports; durable exhaustive hard purge with failure/restart/restore handling; shared quotas and worst-case spend reservations, independent aggregates that survive guest deletion.
5. **GE-08/09:** public route boundary/landing, then guest entry/status/expiry/locked-social/copy variants. Never auto-create a Supabase identity on public page load, silently replace a registered session or recover old data in a new trial.
6. **GE-10/11/12:** separate unlinked feedback table and expiring submission receipts; strict API/anti-spam/retention; independent registered-admin authorization; accessible rating-only/optional-category/comment form and minimal admin aggregates/status table.
7. **GE-13:** optional short route-aware tour, stable DOM targets, skip/back/finish/replay, guest/registered differences. Driver.js is a candidate only: prove exact pinned version under React19/StrictMode/CSP/keyboard/SR/mobile/reduced motion before adding one dependency. Preserve native dialog/focus/GSAP behavior; no tour-triggered data mutation.
8. **GE-14:** integrated journey/regression/security/capacity and release evidence. Prepare reviewed migrations/config/images/rollback and stop at explicit release decision.

Non-negotiable guest requirements:

- A new independent browser gets an independent provider/internal identity, no email/password. Server grants T0 using fresh DB time; deadline T=T0+**7200 seconds**. At T authorization fails. No sliding extension, refresh/retry/tab/restart reset or expired-session reauthorization.
- Frontend timer is informational. Backend predicates, SQL helper, transaction final checks and background policies enforce the deadline; close idle streams and discard late provider output. Never dispatch or authorize new paid work after T. Already dispatched provider work, preauthorized transport delivery and user-downloaded copies cannot be recalled; do not promise otherwise.
- All personal data remains isolated. No real matching/discovery/connection/human-message/shared-activity/reveal/staff access. Cầu Nối can give general advice; existing structured quiz/focus needs a connection and is forbidden to guests; solo structured mode is deferred.
- Conversations/messages/proposals/memories/vectors/jobs/moods/age/consents/events/app sessions/usage/receipts/exports/guest records/provider identity must purge. No silent retention of UUID-linked guest data. Check foreign-key variants, not only `user_id`. Cleanup failure never restores access. Persist a random provider correlation before signup and pass it through `anonymous_session(captcha_token, *, correlation_id)`; narrow guarded helpers reconcile a crash before subject persistence. An ambiguous attempt must never automatically issue another upstream signup.
- Maintain normal16+/18+ and consent/approval/privacy checks. Do not enable history, semantic memory, microphone or MATCH silently. Guest history/proposals/exports expire no later than T.
- Initial proposed guest quotas are25 AI turns/trial,6/minute,1active; initially10 concurrent guest AI calls within global capacity. Voice6clips/180seconds/trial,2/minute,1active/guest and3global. Preserve registered headroom; counters survive restart/midnight/credential rotation. Financial cap requires an owner-approved nonzero dollar budget, known pricing and reservations for AI/STT/embed/uncertain calls.
- Retained voluntary feedback is independently disclosed, contains no user/provider/session IDs or private activity, and survives guest purge only under approved policy. Rating1–5 required; categories/comment optional; comment≤1000codepoints. No automatic conversation/journal/audio/screenshot attachment or persistent private draft.

Outstanding owner release decisions are D01–D04 in07: exact public cleanup/backup/provider/security-counter disclosure and operational target; numeric guest daily spend budget; proposed180-day unlinked feedback retention; approved non-production hosted Auth target and later release authorization. You can implement with flags off while these are unresolved, but must not enable public collection/paid trial or claim release readiness. Universal every-copy erasure at exactly2h remains blocked unless a different approved architecture can substantiate it. Do not silently reinterpret it as a TTL promise.

Testing is required for every feature. Follow exact proposed tests in06, using disposable local `_test` DBs and synthetic provider/model/audio data. Add failing regression tests before behavior implementation. Include exact boundary (`T−1ms`, `T`, `T+1ms`), request/commit/output races, multiple browsers/tabs, CSRF/direct API denial, orphan cleanup, provider revocation, embeddings/job retry/restart, cleanup outage, budget after guest purge, retained feedback unlinking, admin role/reauth/flag gates, callback preservation and optional tour accessibility. Do not freeze Python time and assume database time froze too.

Run relevant lint/type/unit/API/PostgreSQL/migration/contract/frontend build/fixture/browser/fullstack checks, then broader CI-required checks. Existing scripts and safe command examples are in06 and `docs/development.md`. Generate OpenAPI/TS only through repository tools and inspect drift. Do not weaken assertions, skip failing security tests, mock the complete behavior, remove features, increase timeouts or reduce load solely to get PASS. Explain new and preexisting failures separately.

Audit baseline evidence to preserve: ruff/mypy passed;642 backend tests passed;73 frontend unit tests passed;44 selected fixture browser tests and28 synthetic fullstack tests passed; migration head0015/check passed. Build warned about528.02kB main JS. First50-user one-worker load failed at SSE completion with TimeoutError while fullstack was active; same isolated rerun passed, AI p95≈7.63s, non-AI p95≈1.41s. Cause of first failure was not proven and no production capacity was certified. Windows deployment poller tests were partial because `fcntl` is unavailable; run unchanged Linux tests before release. Hosted anonymous flow/CAPTCHA/provider retention/backup restore and future features were not verified by those baseline passes.

Deliver implementation evidence by task: files changed and why, exact commands/result counts, migration/contract review, browser viewport/keyboard/SR evidence, observed cleanup/provider/budget outcomes, failures/skips and remaining decisions. Use a final concise table of scope/changes/executed commands/outcomes/coverage/unresolved risks and **PASS/PARTIAL/FAIL**. Record a final QA summary under repository conventions. Commit focused changes only on the feature branch; keep generated browser artifacts/secrets out of commits.

Stop before production migrations, Dashboard toggles, merge or deployment until the owner explicitly approves the concrete release decision. Provide a safe guest-aware rollback: disabling entry must leave deadline enforcement and cleanup running, and rolling back to an old image that treats guests as registered is forbidden.

---

This prompt is the final handoff artifact. Its presence does not indicate that any implementation step has been executed.
