# Diary Experience V2 implementation plan

Implementation checkpoint: D01?D07 are implemented and locally verified; D08 finishing is recorded in the [current ledger](14-implementation-progress.md). The original planning baseline below is preserved.

Date: 2026-10-29. Base: `9ca7fc8`, branch: `feat/diary-experience-v2`.

**Goal:** a private Vietnamese journal with multiple moments per day, text and media, a calendar, timeline, and evidence-backed help from the existing Nhịp.

**Architecture:** extend the React 19/Vite SPA and FastAPI modular monolith. Keep `moodprint.moods` and its one-per-day APIs unchanged; add owner-scoped journal tables. Supabase private Storage delivers media directly, while the backend grants bounded upload/read capabilities. Only Nhịp receives the new read tool.

**Tech stack:** existing SQLAlchemy/psycopg, Alembic, Pydantic, httpx, React Router, GSAP/`@gsap/react`, pytest, Vitest, Playwright and axe.

**Spec:** [requirements](../../diary/requirements.md), [reference inventory](../../diary/visual-references/README.md).

## Global constraints

- Preserve all six PNGs, existing user data, main and `.gitignore`.
- Commit plans before significant product code; logical feature commits; Draft PR only.
- No merge, deploy, production DDL, production bucket changes or destructive tests.
- Vietnamese copy, warm off-white/sage/dark green, WCAG 2.2 AA where applicable.
- Mobile discovery follows composition; keep the existing shell and bottom safe area.
- Preserve legacy mood-note privacy. Journal read access does not authorize memory, embeddings, transcription or sharing.
- Verification statuses are PASS / PARTIAL / BLOCKED / NOT_STARTED; mocked integration never proves hosted integration.

## Approaches and ruling

Extending `Mood` would break its unique day key, 120-character DTO and mood-only AI evidence. Replacing the mood module would risk existing data and API consumers. **Chosen by engineering judgment within the supplied brief:** additive journal domain, retain legacy mood UI at a secondary route. No historical backfill invents creation times or grants AI access to old notes.

The six supplied references settle the visual direction. Impeccable is used as an extension of the incumbent token system, not a new identity exercise. The user's explicit autonomous execution instruction supersedes skill confirmation gates. Native implementation plus bounded parallel subsystem work and fresh review is authorized by the applicable dispatching/review workflows.

## Review focus

1. Interrupted upload after an entry is created: keep recoverable draft and immutable media reservation.
2. Duplicate submission or stale version: replay receipt or reject with 409; never create accidental duplicate entries.
3. Midnight, timezone changes and empty calendar dates: use account day and explicit stored date, never infer mood.
4. Entry deletion after Nhịp retrieval: invalidate the run before final output and exclude derivatives from later model context.
5. Account deletion during failed Storage deletion: durable cleanup outbox must survive removal of the account.

See [roadmap](11-implementation-roadmap.md) for test-first steps and interfaces. All implementation remains NOT_STARTED at this planning commit.
