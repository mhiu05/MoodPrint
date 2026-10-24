# Durable memory lifecycle implementation

> Partly superseded by the 2026-10-24 continuation. Approval validity now uses the AI/MEM consent versions recorded on each proposal instead of the global `data_version`, and AI/MEM withdrawal erases pending previews. See [README.md](README.md).

Implemented in `backend/app/ai/memory.py`, `memory_models.py`, migration `0008_memory_proposals.py`, and `backend/tests/test_memory.py`. No commits or `.gitignore` changes were made by this task.

| Scope | Result |
| --- | --- |
| Persistence | PostgreSQL proposals with pending/approved/rejected/expired transitions, owner scope across valid login sessions, 15-minute preview expiry, row locking, maximum 100 pending proposals per owner. |
| Decisions | Confirmation/rejection receipts and payload digests persist on the proposal; same decision/payload replays across different request keys. Conflicting content or decision returns 409. Unique existing `Memory.proposal_id` plus owner/proposal locks prevents duplicate memory creation. |
| Authorization | Current authenticated actor and user eligibility locked for mutations; approval rechecks AI/MEM consent, user data version, proposal version, source owner/status/version. Cầu Nối proposals forbidden by helper and database constraint. |
| Privacy | AI cannot approve. Approved/rejected/expired previews erase their text; the approved resource owns its text. Terminal proposal metadata/receipts have a 30-day replay window, then bounded cleanup removes up to 1,000 rows per tick. |
| Memory management | Owner can list/edit/delete stored memories with AI disabled. Edit invalidates old embeddings and queues eligible new version; delete clears text and invalidates derived data. Source lineage is preserved during edits. |
| Integration | Root includes router and calls producer from runtime. Direct embedding hooks use the completed embedding module. Retention must invoke both `expire_proposals(db)` and `purge_proposals(db)`. Root handles account deletion and source-driven invalidation outside these owned files. |

## Executed verification

Only local disposable PostgreSQL databases on `127.0.0.1:16432` were used. Neither hosted Supabase nor real provider calls were used.

| Command | Observed result |
| --- | --- |
| `docker exec moodprint-ai-memory-pg createdb -U postgres moodprint_memory_test` | Exit 0; private disposable database created. |
| `uv run --locked pytest tests/test_memory.py -q` with local test DB | Initial regression: 1 failed / 2 passed; a new-key retry returned 404 after confirmation. Durable producer tests then showed expected failures until root router/settings integration. |
| `uv run --locked pytest tests/test_memory.py -k another_valid_login -q` | RED: approval retained preview text; then implemented text erasure. |
| `uv run --locked pytest tests/test_memory.py -k old_terminal -q` | RED: missing terminal purge helper; then implemented bounded cleanup. |
| `uv run --locked pytest tests/test_memory.py -q` | Final targeted run: **10 passed in 13.98s**. |
| `uv run --locked ruff check app/ai/memory.py app/ai/memory_models.py tests/test_memory.py alembic/versions/0008_memory_proposals.py` | All checks passed. |
| `uv run --locked mypy app/ai/memory.py app/ai/memory_models.py` | Success; no issues in two source files. |
| `uv run --locked pytest -q` | First full run: **197 passed, 1 failed in 122.40s**. Failure: embedding retrieval distance expression incorrectly processed a float as vector; embedding implementer subsequently fixed return type and reported its tests passing. Full rerun recorded below when complete. |
| `docker exec moodprint-ai-memory-pg createdb -U postgres moodprint_memory_migration_test` | Exit 0; separate migration database created. |
| `uv run --locked alembic upgrade head` and `uv run --locked alembic check` with explicit local migration DB | Both exit 0; no new upgrade operations detected. SQLAlchemy emitted a warning about reflection of `extensions.vector` type. |

Coverage includes runtime replacement, a second valid same-owner login, foreign owner denial, five concurrent confirmations creating exactly one memory, same/new key replay, contradictory decision, edited payload conflict, persistent expiry and text erasure, stale source/version, forbidden bot, revoked/stale consent context, rejection replay, AI-off memory management, and terminal metadata cleanup.

Memory scope status: **PASS** for targeted behavior/static checks/migration evidence. Overall integration remains subject to root's final combined backend/browser verification and documentation.
