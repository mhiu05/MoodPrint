# Diary V2 implementation roadmap

> For agentic workers: execute test-first; use `executing-plans` for inline work and bounded parallel domain work under `dispatching-parallel-agents`. Track actual results in14. The user explicitly authorized continuous execution in the current checkout.

**Goal:** implement the six experiences without weakening existing privacy or losing historical mood data.
**Spec:** `docs/diary/requirements.md`; architecture/contracts in00–09.

| Task | Priority / dependency | Target files | Required change / acceptance | Tests / complexity / initial status |
| --- | --- | --- | --- | --- |
| D01 | P0 / none | `docs/diary`, this directory | Preserve six original PNG hashes; audit source; write15 concrete docs before code, commit separately. | Git branch+hash verification; M; PASS at planning commit |
| D02 | P0 / D01 | `backend/app/modules/journal/{models,schemas,service,routes}.py`, Alembic0019, main/revisions | Add entries/media/outbox; owner CRUD, drafts, bounded filters, multiple/day, versions/receipts, private runtime-only ACLs. | `test_journal.py`, schema/migration tests; L; NOT_STARTED |
| D03 | P0 / D02 contract | `journal/storage.py`, `journal/media_routes.py`, config/CSP, provisioning docs | Private direct upload/resume/completion/read; queued deletes/orphans; no media memory proxy or public URL. | `test_journal_storage.py`, fake provider, cross-owner API; L; NOT_STARTED |
| D04 | P0 / D02 | users/guests lifecycle, retention, scope schemas | Export/erase journal; all_private/account and guest cleanup; durable Storage deletions. | lifecycle, guest inventory/permissions, retention tests; L; NOT_STARTED |
| D05 | P1 / D02-D03 interfaces | frontend journal components, API helpers, RealApp | Responsive editor, draft/media, calendar, timeline, discovery and detail. Historical mood route remains. | Vitest + Playwright six experiences and failure states; L; NOT_STARTED |
| D06 | P0 / D02 | AI runtime/provider/context/evidence, MessageMarkdown | Nhịp-only bounded saved-entry search and validated links, unchanged mood analysis and other assistants. | AI tool/citation/fence/context regressions; L; NOT_STARTED |
| D07 | P1 / D05 | journal CSS/motion, evidence | Render six widths, polish against references, keyboard/axe and reduced motion. | screenshots/overflow/interaction checks; M; NOT_STARTED |
| D08 | P0 / all | generated contracts, docs14, commits/Draft PR | Run required suites, fix defects, record exact pass/skip/fail and hosted prerequisites, push branch and Draft PR. | build/typecheck/backend/frontend/browser/diff checks; L; NOT_STARTED |

## Interfaces and task steps

D02 produces `JournalEntry`, `JournalMedia`, `JournalStorageDeletion` on shared Base; `schemas` DTOs and collection contract in05. D03 consumes those models and must not redefine owner identity. D04 queues `JournalStorageDeletion` before media/entry removal. D06 consumes `search_for_ai` with the locked User and version. D05 consumes generated camelCase contracts and only ephemeral upload/read capabilities. D07 consumes actual D05 renders; D08 verifies the complete branch.

For each D02–D06:

- [ ] Write a named behavior test: owner isolation/two same-date entries (D02), mismatched completion and failed delete retry (D03), account erasure queue survives (D04), dirty editor/reload/calendar (D05), forged source ID/stale evidence (D06).
- [ ] Run the new tests before production changes; record expected failure from missing behavior.
- [ ] Implement the smallest complete domain change using the exact contract above.
- [ ] Run focused tests and relevant regressions; fix defects before claiming PASS.
- [ ] Parent reviews integration boundaries and commits only intended files as a logical group.

Pre-flight: D02/D03 share models; D02 owns definitions. D03/D04 share deletion outbox; D04 uses queue helper and D03 worker consumes it. D05/D06 share citation route; `/self/entry/:id` is canonical, safe renderer is D06-owned. No `.gitignore` or existing agent/skill config changes. A fresh whole-branch review follows integration; review findings receive regression tests and fixes.
