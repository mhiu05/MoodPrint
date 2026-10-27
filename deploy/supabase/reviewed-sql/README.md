# Reviewed Supabase SQL

SQL that `scripts/apply_supabase_review.py` and `scripts/provision_supabase_runtime.py` execute against the hosted project, one file at a time, **only** after the operator passes that file's SHA256 as `--approved-sha256`.

- `MANIFEST.json` pins each file's SHA256, size and where it was recovered from. Being listed there is a record of what was approved, not permission to run it.
- The bytes are the unmodified Git blobs of commit `41e27c7^`; `docs/` was deleted in `41e27c7`. `.gitattributes` turns newline conversion off for `*.sql` here so a Windows checkout keeps the approved hash.
- `python scripts/check_reviewed_artifacts.py` (run in CI) fails if a pinned file is missing or differs by one byte, if SQL appears here without a manifest entry, or if a script points anywhere else. Adding or changing SQL means a new review, a new hash and a manifest update in the same change.
- Apply reports are written to `deploy/supabase/reports/` (not tracked content; created on demand).
