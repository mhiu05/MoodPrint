# Implementation progress

Plan: [2026-10-25-moodprint-productization-implementation.md](../../plans/2026-10-25-moodprint-productization-implementation.md) · Branch: `docs/productization-plan` · Statuses: NOT_STARTED · IN_PROGRESS · PASS · FAIL · BLOCKED.

"Commit" is the commit that completed the task (`git log --grep "<task id>"` lists all of them). Test counts are the counts observed when the task was closed.

| Task | Status | Commit | Tests executed | Results | Known limitations |
|---|---|---|---|---|---|
| A-01 | PASS | see `git log --grep A-01` | VC-DB `prod_test`; ruff; mypy; pytest; typecheck; vitest; mocked Playwright | ruff PASS; mypy 61 files; pytest 278 passed; vitest 89; E2E 34 | Full-stack not run at baseline ([baseline.md](baseline.md)) |
| A-02 | PASS | see `git log --grep A-02` | guard RED (2 failed) → GREEN; vitest; typecheck; build; dist grep; mocked Playwright; `test_production_imports.py` | vitest 14 passed (12 existing + 2 guard); typecheck/build exit 0; `Mô phỏng|bản mẫu|fixture=` in dist: 0; E2E 34 passed; backend guard 1 passed | — |
| A-03 | PASS | see `git log --grep A-03` | UI-export guard RED (1 failed) → GREEN; typecheck; vitest; build; mocked Playwright; VC-FS | vitest 15 passed; E2E 34 passed; full-stack 13 passed (axe included); CSS bundle 52.6 kB → 26.8 kB; `docs/mvp-validation/screens` byte-identical except random aliases and one loading-state capture | First prune pass wrongly dropped `.conversation-welcome > p:not(.overline)` (hero text size); caught by screenshot review, pruner fixed to ignore `:not()` and re-run |
| A-05 | PASS | see `git log --grep A-05` | `test_outbox_retired.py` RED (2 failed) → GREEN; retention + social regression | 2 passed; with `test_retention.py` + `test_social.py` 14 passed; `git grep "Outbox(" backend/app` → only the model | Table kept until a post-MVP contract migration |
