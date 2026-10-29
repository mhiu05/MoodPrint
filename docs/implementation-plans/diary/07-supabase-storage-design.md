# Supabase Storage design

Status: NOT_STARTED; hosted integration remains unverified until configured in an authorized non-production environment.

Private bucket `journal-media`; paths derived by backend: `users/{app_user_uuid}/{entry_uuid}/{image|audio|video}/{media_uuid}.{safe_extension}`. Ignore original filename for object identity. MIME allowlist excludes executable content/SVG. Initial per-file maxima: image10/audio20/video50 MiB; bucket global maximum at least50 MiB. Ten active attachments/entry; browser uploads one at a time to bound bandwidth and retry scope.

## Control and delivery

Backend uses a new SecretStr server credential (never VITE_ or DTO/logged). A service adapter signs exact new object uploads with upsert disabled. Completion checks provider object metadata against the reserved MIME/length before the row is readable. Sign reads for approximately 60 seconds only after current owner authorization. Browser requests a fresh link when needed, uses images lazily and audio/video preload=none. No public bucket or stored permanent access URL.

Supabase recommends resumable TUS uploads above6MB or unstable networks. Use signed upload token with `x-signature`, 6MiB chunks, bounded retries and progress; do not introduce a browser provider session/JWT. Signed upload tokens last2hours: disclose this capability lifetime in operational docs, never claim instantaneous revocation. Pending rows are cleaned after24hours and repeated remote-delete jobs handle abandoned bytes.

Entry/media/account deletion writes a durable outbox before metadata removal. Worker removes object with provider API outside owner transactions, retries failures, deletes job only on confirmed absence/deletion. Queue path contains owner UUID, so retain it only while deletion is outstanding. No AI processing of bytes/transcripts is enabled here.

## Provisioning (review only)

Provide repeatable SQL/config for a PRIVATE bucket with allowed_mime_types and file_size_limit=52428800. Enable owner-only capability flow by denying direct authenticated/anon object access in this bucket; application-owned UUIDs are not Supabase auth subjects. Never weaken unrelated bucket policies. Supabase service role bypasses RLS, so application ownership checks are mandatory before signing and completion. The private DB schema follows runtime-only RLS, not a misleading auth.uid policy.

CSP permits only the configured Supabase HTTPS Storage origin for connect/img/media. No wildcard, data token in analytics, or service key in frontend. Exact hosted CORS/limits/RLS/URL expiry must be verified separately.

## Documentation checked

- [Resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads): TUS, signed x-signature, 6MiB chunks, immutable paths.
- [Signed uploads](https://supabase.com/docs/reference/javascript/file-buckets-createsigneduploadurl):2-hour upload capability.
- [Private buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals): signed owner reads.
- [Changelog](https://supabase.com/changelog): read on2026-10-29; TLS-cipher deprecation applies to HTTP clients, use current httpx/runtime TLS defaults.

The repository uses Alembic, not Supabase declarative schema generation; keep that migration convention. No production project was queried or mutated.
