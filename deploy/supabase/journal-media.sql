-- REVIEW ONLY. Run only against an explicitly approved non-production/production target.
-- App user UUIDs differ from auth subjects: BFF validates owners and issues exact signed capabilities.
-- No browser/general-purpose role may read or write journal-media objects directly.
BEGIN;
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('journal-media', 'journal-media', false, 52428800, ARRAY[
 'image/jpeg','image/png','image/webp','image/gif',
 'audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav',
 'video/mp4','video/webm','video/quicktime'
])
ON CONFLICT (id) DO UPDATE SET public=false,
 file_size_limit=EXCLUDED.file_size_limit, allowed_mime_types=EXCLUDED.allowed_mime_types;

-- A restrictive fence also protects this bucket if another bucket has an overbroad permissive policy.
DROP POLICY IF EXISTS journal_media_bff_only ON storage.objects;
CREATE POLICY journal_media_bff_only ON storage.objects AS RESTRICTIVE
 FOR ALL TO anon, authenticated
 USING (bucket_id <> 'journal-media') WITH CHECK (bucket_id <> 'journal-media');
COMMIT;
