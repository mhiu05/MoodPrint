# A-01 — Baseline snapshot

Date: 2026-10-25 · Branch: `docs/productization-plan` at `4a9cb45` (planning commit on top of `main` `5689dd9`). Per the session instruction, implementation continues on this branch instead of `feat/productization`.

Working tree before any change: ` M .gitignore` (user-owned; never staged).

| Check | Command | Result | Duration |
|---|---|---|---|
| Disposable DB | VC-DB `prod_test` on `moodprint-ai-memory-pg` (127.0.0.1:16432) | created | — |
| Ruff | `cd backend && uv run --locked ruff check app tests evals alembic` | PASS — "All checks passed!" | — |
| mypy | `uv run --locked mypy app` | PASS — "no issues found in 61 source files" | — |
| pytest | `uv run --locked pytest -q` (TEST_DATABASE_URL → `prod_test`) | PASS — **278 passed** | 247 s |
| Frontend typecheck | `cd frontend && npm run typecheck` | PASS (exit 0) | — |
| Vitest | `npx vitest run` | PASS — **89 passed** (5 files) | 1.1 s |
| Mocked Playwright | `npx playwright test` | PASS — **34 passed** | 57 s |
| Full-stack | VC-FS | NOT RUN at baseline (run at phase milestones; rewrites tracked visual baselines) | — |

Pre-existing failures: none.

Note: mocked Playwright rewrites tracked files under `frontend/evidence/` (`e2e-results.json`, `playwright-report/index.html`, two `ai-chat-memory/mock-*.png`). They are restored with `git checkout -- frontend/evidence` after each run; results are recorded in these evidence files instead.
