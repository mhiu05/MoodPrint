# MoodPrint Productization — Document Index

Planning set produced on 2026-10-25 against revision `5689dd9`. Analysis, design and plans only; no application code was changed.

**Start here:** [14 — Implementation handoff](14-implementation-handoff.md) → [implementation plan](../plans/2026-10-25-moodprint-productization-implementation.md).

| # | Document | Purpose |
|---|---|---|
| 00 | [Executive summary](00-executive-summary.md) | One-page status, scope, roadmap, decisions needed |
| 01 | [Codebase audit](01-codebase-audit.md) | Evidence-based feature classification, defects, risks, verification run |
| 02 | [Prototype removal inventory](02-prototype-removal-inventory.md) | DELETE / MIGRATE / REFACTOR / KEEP / KEEP_FOR_TESTS per path |
| 03 | [Product requirements](03-product-requirements.md) | Requirement IDs, MVP vs post-MVP, metrics, traceability |
| 04 | [Target architecture](04-target-architecture.md) | Modules, sync design, concurrency, topology limits |
| 05 | [Matching design](05-matching-design.md) | `rules-v2` scorer, retrieval SQL, fairness, evaluation |
| 06 | [Shared activities design](06-shared-activities-design.md) | Framework, state machines, schema, API, both-screen flows |
| 07 | [Database and API contracts](07-database-and-api-contracts.md) | Migrations 0011–0014, DTOs, errors, settings |
| 08 | [Frontend UX plan](08-frontend-ux-plan.md) | Screens, components, states, viewport acceptance |
| 09 | [Security, privacy, operations](09-security-privacy-operations.md) | Threats, moderation, retention, monitoring, backups |
| 10 | [Testing and evaluation strategy](10-testing-evaluation-strategy.md) | Commands, test catalog (T-*), patterns |
| 11 | [Migration and rollback](11-migration-and-rollback.md) | Sequence, hosted procedure, rollback matrix |
| 12 | [Release readiness](12-release-readiness.md) | Release trains, go/no-go gates |
| 13 | [Risks and decisions](13-risks-and-decisions.md) | Decision records D-*, open questions Q-*, risk register |
| 14 | [Implementation handoff](14-implementation-handoff.md) | Fresh-session entry point |

Superpowers-format artifacts:

- [Design (brainstorming format)](../plans/2026-10-25-moodprint-productization-design.md)
- [Implementation plan (writing-plans format)](../plans/2026-10-25-moodprint-productization-implementation.md)

Historical plans under `docs/plans/00…10-*.md` (Vietnamese) remain the record of the previous program and are validated by `scripts/check_plans.py`; this set supersedes them for the productization program.
