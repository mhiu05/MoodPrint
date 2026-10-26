# Privacy and feature availability verification — 2026-10-26

Scope: local implementation branch `feat/privacy-availability`, synthetic accounts and a disposable PostgreSQL database. No production data, live OpenAI/Voyage calls, Supabase migration or deployment were used.

| Check | Observed result |
|---|---|
| `uv run --locked ruff check app tests` | PASS |
| `uv run --locked mypy app` | PASS, 87 source files |
| `uv run --locked pytest -q tests/test_memory.py tests/test_matching_lifecycle.py tests/test_voice.py tests/test_chat_persistence.py tests/test_privacy_lifecycle.py tests/test_matching_privacy.py` with local `TEST_DATABASE_URL` | 62 passed |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd test` | 10 files, 54 tests passed |
| `npm.cmd run build` | PASS, Vite production bundle built |
| `npm.cmd run test:e2e -- tests/e2e/activities.spec.ts tests/e2e/admin.spec.ts tests/e2e/auth.spec.ts tests/e2e/chat-history.spec.ts tests/e2e/discovery.spec.ts` | 37 passed |
| `npm.cmd run test:e2e -- tests/e2e/real.spec.ts tests/e2e/social.spec.ts tests/e2e/states.spec.ts` | 29 passed |
| Focused responsive test at 390, 768 and 1280 px | 1 passed |
| `uv run python ../scripts/test_fullstack.py chat-history.spec.ts journeys.spec.ts local-mvp.spec.ts mvp.spec.ts` with local `TEST_DATABASE_URL` | Initial run: 12 passed, 2 test setup/locator failures; all 14 passed across the initial run and focused rerun of `local-mvp.spec.ts mvp.spec.ts` (7 passed) after repair |
| `uv run python ../scripts/test_fullstack.py responsive.spec.ts` with local `TEST_DATABASE_URL` | 1 passed |
| `uv run python ../scripts/load_social_mood.py --users 10` with local `TEST_DATABASE_URL` | 2 runs failed the existing 500 ms read p95 gate for `/session` (697 and 939 ms); no HTTP, isolation or integrity failures |

The single combined Playwright command hit its 180-second suite timeout while PostgreSQL tests ran concurrently: 55 cases had passed and 10 had not run. No assertion failed in that attempt. Every case subsequently passed in the split runs above. The first PR CI run then failed six full-stack tests because their setup still expected global AI and matching enable buttons. The repaired tests use first send, explicit publication and the revocation disclosure; a controlled checkbox test now waits for the server response. A later CI attempt had a load-gate failure and a transient contrast audit failure at 430 px; the load script now prints the failed acceptance criterion, and the responsive audit uses reduced motion to inspect settled colors. The performance gate remains unchanged. CI must pass before merging.

Added regression coverage checks first AI send, per-item memory approval and rejection, sibling proposals, unpublished matching drafts, explicit publication and unpublication, 30-day cap for new saved conversations, Voyage opt-out persistence, user-initiated microphone access, permission denial and cancellation of an in-flight STT request.

No database schema migration was needed; existing `consents`, `consent_events`, `ai_preferences`, memory proposals and published profile fields represent the new flow. Existing permission values and saved data were not rewritten. The rollback and privacy boundaries are documented in [privacy-availability](../privacy-availability.md).
