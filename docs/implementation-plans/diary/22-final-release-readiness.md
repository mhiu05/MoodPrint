# Final release readiness

Verdict: **READY_FOR_REVIEW**. Not ready for production release.

## Ready for review

- Personal timeline, composer copy, 90-day explanation, and text-only Nhịp contract are on `feat/diary-experience-v2`.
- User-facing export buttons and dialogs are removed. Account deletion and guest end remain.
- Frontend typecheck, unit tests, production build, and 100 Playwright tests passed locally.
- Hosted project identity, revision `0018_app_feedback`, absent journal tables, and a private `journal-media` bucket were read from the configured project. No hosted DDL was run.

## Not ready for release

1. Hosted migration `0019_journal` is **applied** and the compatibility image stayed ready. See [17](17-hosted-migration-verification.md). This diary application still must not be merged until its own CI is green on the merge that keeps readiness at `0019_journal` only.
2. Provider daily backups are still empty and PITR is off. Recovery of the application schema was rehearsed from the logical dump taken immediately before the upgrade. That does not restore Storage objects or Supabase-managed schemas.
3. Authenticated export routes remain. See [19](19-export-removal-audit.md).
4. The new Nhịp payload assertion and the updated fullstack export journeys were not re-run against PostgreSQL here.
5. No production image of this branch has been deployed yet. The database is now `0019_journal`, so this branch may merge after CI passes on the resolution that accepts only that revision.

## Release order when authorized

1. Review this draft PR.
2. Ship an application whose readiness accepts `0019_journal` only after the schema is migrated, or ship an explicit compatibility revision list first. Do not point production traffic at this branch while the database is still `0018_app_feedback`.
3. Approve a new `0018` → `0019` SQL artifact. Do not rewrite pinned SQL.
4. Confirm a restorable backup, rehearse the upgrade, then apply it.
5. Confirm `alembic_version`, the three journal tables, runtime grants, RLS, unchanged mood rows, and the private bucket.
6. Roll back by serving the previous application image. Do not drop journal tables to roll back.

## Risks

- Production readiness fails if 0019 is applied before the new application is the one being served.
- Production journal routes fail if this application is served before 0019 exists.
- People who relied on the settings download no longer have a button. The API still performs an owner-scoped copy until a later decision removes it.
- WAL-G is enabled, but the backup list is still empty and PITR is off. Recovery of the application schema was rehearsed from the logical dump. That does not restore Storage objects or Supabase-managed schemas.
