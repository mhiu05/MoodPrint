# Journal upload release fix — 2026-11-04

## Incident and scope

The released journal editor could save a text draft, but attachment reservation returned
HTTP 503 `MEDIA_UNAVAILABLE` before any bytes reached Storage. A synthetic PNG reproduced
this through the authenticated UI on `moodprint.duckdns.org`.

Two independent deployment omissions were verified:

- `JOURNAL_STORAGE_KEY` was absent from both the running API environment and the AWS
  runtime parameter. Only presence booleans were printed during diagnosis.
- Caddy's document CSP omitted the configured Storage origins from `connect-src`,
  `img-src`, and `media-src`, blocking direct uploads and signed reads even with a key.

The existing `journal-media` bucket is private, limits files to 50 MiB, and has the
expected MIME allowlist. `storage.objects` has RLS enabled and no policies, which keeps
browser roles denied by default. No application migration or policy change is required.

## Fix and rollout

`deploy.sh` derives public origins from the API environment resolved by Docker Compose,
including dotenv interpolation. It validates a plain HTTPS origin and, for a Supabase
project origin, includes its exact direct Storage origin. The server credential stays
in the API environment. Compose passes only these public origins to Caddy, which adds
them only to connection, image, and media directives. Unconfigured Storage keeps the
previous same-origin restrictions.

The release poller updates image references; it does **not** install new copies of
`deploy.sh`, `compose.staging.yml`, or `Caddyfile`. Operators must update these three
installed files from the reviewed commit, retain protected backups, validate Caddy,
and recreate the web container so its origin environment changes. A plain Caddy reload
cannot update container environment variables. Preserve the existing Caddy bind mount
inode when writing its contents.

Set the existing server-side Storage credential in the protected runtime parameter,
then use the normal deployment script with the current verified immutable image pair
and release SHA. Keep all other runtime settings unchanged. Do not expose the credential
in command arguments, output, the web container, documentation, or frontend assets.
Rollback restores the installed files, previous runtime parameter version, and previous
Compose environment; validate health and the resulting document CSP after either action.

## Verification before PR

- Red: original Caddy configuration rejected the new Storage-origin assertion; the
  deployment origin derivation was missing. The interpolation regression also failed
  before switching derivation to Compose's resolved API environment.
- Green: Linux `python -m unittest discover -s deploy/aws/tests -v`: **37 passed**,
  including **6 new tests**, 13.715 seconds. Uses an existing local test-tool image and
  synthetic runtime files, with access to the local Docker daemon.
- `bash scripts/test_staging_proxy.sh`: **passed** using local API/web images and the
  updated bind-mounted Caddyfile. Checks actual HTTP CSP with Storage disabled/enabled,
  unchanged script/frame restrictions, health/session routing, and SSE flushing.
- `uv run --locked pytest -q tests/test_journal_storage.py -m 'not postgres'`:
  **6 passed, 10 deselected**, 7.35 seconds; provider HTTP calls are synthetic.
- `uv run --locked ruff check ../deploy/aws/tests/test_journal_storage_deployment.py`:
  passed after sorting imports. No existing test was deleted or relaxed.

Full live upload/save/reload verification, independent final review, remote CI, PR merge,
and the applied host configuration are recorded after execution. Until then, these
local results do not establish that the deployed incident is resolved.
