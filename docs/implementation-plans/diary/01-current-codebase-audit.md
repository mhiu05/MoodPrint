# Current codebase audit

Audit baseline: `9ca7fc8`; read-only inspection on 2026-10-29. Status: PASS (source inspection, not runtime certification).

| Area | Actual implementation | Reuse / change |
| --- | --- | --- |
| Daily mood | `backend/app/infrastructure/database/models.py::Mood`; unique `(user_id, local_date)`, note 120, version | Preserve table and `modules/mood/routes.py` PUT-by-day, 90-day list/summary. |
| Existing UI | `frontend/src/features/real/Mood.tsx::Moods`, `MoodInsights` | Current form uses a select, optional note, 90-day picker and edit/delete; no attachment or calendar. Retain legacy access. |
| Shell | `features/real/RealApp.tsx`, `real.css`, `styles/tokens.css` | Retain desktop rail, five mobile destinations, session context and account timezone. |
| Contracts | `backend/app/contracts.py::DTO`; `frontend/src/api/client.ts` | camelCase, extra fields forbidden, CSRF and idempotency on writes. Generate OpenAPI/TS after routes. |
| Authorization | `backend/app/core/security.py::require_actor`, `transaction` | Session/provider checks, owner lock, eligibility, deletion and guest deadline fence. Add owner predicate to every journal query. |
| Concurrency | `previous_receipt`, `save_receipt`, `User.data_version` | Replay writes; explicit expectedVersion; increment data version and invalidate AI on source mutations. |
| Voice | `modules/voice`, frontend recorder | Existing STT requires AI/VOICE and does not preserve playable audio. Use MediaRecorder separately; do not auto-transcribe. |
| AI | `ai/runtime.py`, `provider.py`, `evidence.py`, `context.py` | Existing five bots; Nhịp's explicit mood-scope flow uses deterministic `MoodAnalysisPlan`. Keep that path intact. |
| Legacy privacy | `modules/mood/service.py::selected_summary` selects date/value/version only | Never expose old `Mood.note` to the new tool. |
| Storage | No existing journal Storage adapter | Add private bucket adapter, server configuration, direct capability upload and lazy signed reads. |
| Migrations | Alembic head `0018_app_feedback`, `core/revisions.py` readiness | Add 0019, do not rewrite earlier migrations or pinned reviewed SQL. |
| Lifecycle | `modules/users/routes.py`, `users/lifecycle.py`, `guests/lifecycle.py`, `jobs/retention.py` | Add explicit export/delete/retention and exhaustive guest inventory classification. |
| Tests | `backend/tests/conftest.py`, `test_mood.py`, SDK/context/guest tests; frontend Vitest + fixture/fullstack Playwright | Disposable local PostgreSQL required for integration, separate fresh Alembic verification. |

The current CSP in `backend/app/main.py::content_security_policy` permits self/blob media only. Direct Supabase uploads and signed reads need an exact configured Storage origin in connect/img/media policies, never a wildcard.

`docs/supabase/migrations.md` contains older hosted-runner statements; `scripts/apply_supabase_review.py` and pinned manifest already include 0018 and are authoritative. Existing reviewed SQL must stay byte-for-byte unchanged. There is no Codespace here: this is the user's Windows checkout at `E:\MoodPrint`; workflow requirements are applied to this checkout.
