# Private Profile Notes Retirement Implementation Plan

> **For agentic workers:** Implement the plan task by task in the current workspace; preserve unrelated pre-existing edits.

**Goal:** Retire private profile notes end to end, erase their stored data on migration, and preserve approved AI memories.

**Architecture:** Remove the private-item UI, API, AI proposal variant, and database model while retaining account identity fields, profile taxonomy, and AI memory resources. A forward-only Alembic migration clears private-item data and obsolete source links before dropping the table and related columns.

**Tech Stack:** React, TypeScript, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/Supabase.

**Spec:** `docs/superpowers/specs/2026-10-30-private-profile-retirement-design.md`

## Global Constraints

- Preserve approved AI `Memory` records and their embeddings.
- Purge private-item records and private-item proposals; expire pending memory proposals sourced from deleted private items.
- Keep `/taxonomy`, identity sharing, account support, moods, journals, and social profile behavior.
- Do not modify `.gitignore` or other unrelated pre-existing workspace changes.
- Do not apply the migration to a hosted Supabase database.
- Do not add or run tests; update existing test expectations only where their contract is removed.

## Review Focus

- Pending memory proposals with deleted private-item sources must be expired and have their text cleared.
- Approved memories must survive the migration with their source links removed.
- AI runtime must no longer create `private_item` proposals, while memory proposals remain reviewable.
- Account cleanup, export, and guest cleanup must not query a removed table or accept obsolete private-item scopes.
- `/taxonomy` and identity sharing must remain available after removing private-item API routes.

---

### Task 1: Remove private-note user flows

**Files:** `frontend/src/features/real/RealApp.tsx`, `frontend/src/features/real/Memory.tsx`, `frontend/src/features/real/AssistantGuide.tsx`, `frontend/src/features/onboarding/tourSteps.ts`.

**Interfaces:** Account page retains `OwnIdentity`, `AdultEligibility`, and `AccountActions`. Memory page continues to consume `/memories` and `/proposals` for memory-only proposals.

- [x] Remove private-note form, list, editing/deletion state, and obsolete imports from the account page.
- [x] Keep the account heading, identity section, eligibility section, and account actions; retain account actions at the bottom.
- [x] Remove UI branches and guide copy that refer to private-profile proposals or navigation.

### Task 2: Remove private-item APIs and AI proposal behavior

**Files:** `backend/app/modules/profiles/routes.py`, `backend/app/contracts.py`, `backend/app/modules/users/routes.py`, `backend/app/modules/users/schemas.py`, `backend/app/modules/users/lifecycle.py`, `backend/app/modules/guests/lifecycle.py`, `backend/app/ai/runtime.py`, `backend/app/ai/prompts.py`, `backend/app/ai/memory.py`, `backend/app/ai/memory_models.py`, `backend/app/ai/embeddings.py`, `backend/app/ai/schemas.py`, `backend/app/infrastructure/database/models.py`.

**Interfaces:** Profiles router retains `GET /taxonomy`. Memory proposal API becomes memory-only; approved memories and proposal review/delete/edit endpoints remain.

- [x] Remove private-item routes, DTOs, ORM model, export scope, deletion scope, and guest-cleanup references.
- [x] Remove the `propose_private_item` tool and the `private_item` proposal purpose.
- [x] Remove optional private-item source references from proposals and memories; keep memory authorization, approval, and embedding behavior.
- [x] Preserve data-version invalidation where the deleted private-item data changed privacy context.

### Task 3: Add the destructive forward migration

**Files:** Create `backend/alembic/versions/0020_private_profile_retirement.py`; update `backend/app/core/revisions.py` and `docs/supabase/migrations.md`.

**Interfaces:** Migration upgrades `0019_journal` to `0020_private_profile_retirement` and has a forward-only downgrade guard.

- [x] Delete rows for `private_item` proposals; expire pending memory proposals with source IDs and clear their text.
- [x] Clear source links on other proposals and approved memories, preserving approved memories.
- [x] Increment `users.data_version` for users whose private-item context is removed.
- [x] Drop obsolete proposal constraints/indexes/columns, memory source constraints/index/columns, and `private_items`.
- [x] Update readiness and migration documentation for the new revision.

### Task 4: Regenerate contracts and reconcile references

**Files:** `backend/openapi.json`, `frontend/src/api/generated/schema.d.ts`, `frontend/src/api/contracts.ts`, affected docs and existing tests.

**Interfaces:** Generated API contracts no longer include private-item paths, schemas, or export/deletion scopes.

- [x] Regenerate OpenAPI with `python scripts/export_openapi.py` and TypeScript API types with `npm run contracts:generate`.
- [x] Update API, AI, lifecycle, guest-cleanup, and schema documentation to match the retired feature.
- [x] Remove or revise existing test cases that call removed private-item endpoints or expect the removed proposal purpose; do not add tests.
- [x] Review the final diff for remaining private-item runtime references and unrelated workspace edits.
