-- Runtime corpus queries switch explicitly to authenticated and never read licence notes.
-- Ingestion already uses the isolated owner/admin connection (TEST_ADMIN_DATABASE_URL).
-- Keep the original migration immutable; remove the unused runtime write capability here.
revoke all on table knowledge.source_confidential from public, anon, authenticated, service_role, moodprint_api;
revoke all (source_id, licence_note) on table knowledge.source_confidential from public, anon, authenticated, service_role, moodprint_api;

drop policy ingest_writer on knowledge.source_confidential;

-- Retain an explicit deny policy and RLS coverage. Only owner/admin ingestion bypasses RLS.
create policy no_runtime_access on knowledge.source_confidential
  for all to moodprint_api
  using (false)
  with check (false);
