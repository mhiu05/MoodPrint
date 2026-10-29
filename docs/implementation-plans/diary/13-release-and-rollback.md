# Release and rollback

Status: NOT_STARTED. This task ends at a Draft PR; merging, deploying and production mutations are explicitly unauthorized.

## Reviewable change sequence

1. Preserve visual references and commit audited plan.
2. Add additive0019 schema/core routes/lifecycle and tests.
3. Add private Storage control flow, provisioning instructions and synthetic adapter evidence.
4. Add responsive UI/calendar/timeline and extend existing Nhịp with source links.
5. Commit generated contracts, screenshots, verification and fixes in logical groups.
6. Push only `feat/diary-experience-v2`; open Draft PR against main with migration risks and honest integration status.

## Production prerequisites (not executed)

- Review Alembic0019 and generate a new pinned hosted SQL artifact using the existing reviewed migration workflow; do not edit0018 pins.
- Provision private journal-media and server-only credential; check RLS, MIME/50MiB max, CORS and exact HTTPS Storage origin.
- Verify live owner upload/read/delete, resumable interruption, token expiry, orphan/outbox cleanup and bounded worker observability on staging.
- Verify migration/readiness ordering and backup/restore, retention/export/delete behavior with synthetic staging accounts.
- Run CI, review screenshots at six widths and confirm actual hosted provider AI citation behavior with opt-in synthetic data.

## Rollback

Keep additive tables/data and turn traffic back to the previous application image if needed. Existing mood APIs/data are unchanged. Stop new journal capabilities while preserving queued cleanup, not by opening a bucket or dropping tables. Already issued signed URLs may live until expiry. Do not downgrade/drop journal tables in production as an automatic rollback. An authorized later recovery can re-enable the feature over preserved drafts/entries. No force push or main rewrite.
