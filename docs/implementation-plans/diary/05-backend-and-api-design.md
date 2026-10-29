# Backend and API design

Current implementation: **PASS**. All nine journal/media operations are registered in `backend/app/modules/journal/{routes,media_routes}.py` and generated contracts; [14](14-implementation-progress.md) records authorization/receipt tests.

Status: NOT_STARTED. New module: `backend/app/modules/journal/` with models, schemas, service, routes and Storage adapter/routes. Register router under existing `/api/v1` in `app/main.py`.

## Contract

`JournalEntryDTO`: `id`, `localDate`, `timezone`, `mood` (1–5), `text`, `emotions[]`, `factors[]`, `status` (`draft|saved`), `version`, `createdAt`, `updatedAt`, `media[]`.

`JournalMediaDTO`: `id`, `type` (`image|audio|video`), `mimeType`, `sizeBytes`, optional `durationSeconds`, `status` (`pending|ready`), `createdAt`. Object paths are backend-only except the exact scoped upload capability.

| Method/path | Input | Result / guarantees |
| --- | --- | --- |
| GET `/journal/entries` | `from`, `to`, `q`, `mood`, `media`, `status`, `offset`, `limit` <=50 | `{items,total,offset,limit}`, stable date/time/id order; owner predicate before filters. |
| POST `/journal/entries` | localDate, mood, text<=10000, emotions/factors<=12 each, status | Create UUID, version1; Idempotency-Key receipt prevents duplicate submissions. |
| GET `/journal/entries/{id}` | UUID | Owner only, otherwise 404. |
| PUT `/journal/entries/{id}` | create fields + expectedVersion | 409 if stale; receipt replay; invalidate source context. |
| DELETE `/journal/entries/{id}` | expectedVersion | ActionReceipt; durable media deletion jobs then delete entry metadata. |
| POST `/journal/entries/{id}/media` | type, MIME, bytes, duration | Reserve immutable media row and signed upload capability; validate owner, quotas and limits. |
| POST `/journal/entries/{id}/media/{mediaId}/complete` | empty | Verify stored size/MIME with provider before marking ready. |
| GET `/journal/entries/{id}/media/{mediaId}/access` | none | Short-lived signed URL for current owner and ready attachment only. |
| DELETE `/journal/entries/{id}/media/{mediaId}` | empty | Queue remote removal durably; owner-only idempotent response. |

All mutations use existing `require_actor` (CSRF/session/Origin) and `transaction`; owner comes from server `Actor`, not payload/model input. Use `DTO` alias rules and strict bounds. Return existing sanitized DomainError envelope, never provider errors/tokens. Entry/media changes increment `User.data_version`. Reads exclude dates outside active retention until physical purge catches up.

Files upload from browser directly to Storage, not through FastAPI request memory. BFF holds metadata/control calls only. Network provider calls should not occupy a database owner lock; perform capability/verification with authorization before and after the external boundary.
