# Local MVP configuration and verification

All commands below target disposable local data. They do not configure hosted
Supabase, SMTP, AWS or deployment. Never overwrite an existing `backend/.env`.

## Configuration

`backend/local-mvp.env.example` is a non-secret development example. It enables AI,
history capability, activities and matching v2, with accounting off. It retains
60 turns per Bangkok day, 20 requests/minute, two concurrent turns per user and
the global admission limit. A global history flag never opts a user in.

From `backend`, inspect an example or your existing configuration without printing
values or making provider calls:

```powershell
uv run python ../scripts/check_config.py --env-file local-mvp.env.example
uv run python ../scripts/check_config.py --env-file .env
```

`aiConfigurationStatus=ready` means configuration is present and syntactically
plausible. It does **not** validate a remote key, billing state, model permission
or provider availability. Supply both `OPENAI_API_KEY` and `OPENAI_MODEL` through
an ignored `.env` or process environment. The model must support the Responses
API, structured output and function tools used by the existing SDK. No model
name is guessed, no key is invented and no fake provider is used as a fallback.

| Configuration | Service behavior |
|---|---|
| `AI_ENABLED=false` | Service disabled (except the existing development actor allowlist) |
| AI on, key/model empty | `configuration_missing`; no provider request |
| AI on, whitespace inside key/model | `configuration_invalid`; no provider request |
| AI on, key/model present | Admit only eligible, authenticated, consenting users; remote validation happens on the requested turn |
| `CHAT_HISTORY_ENABLED=true`, user history off | Temporary conversation; explain optional saving |
| Global history off | New temporary conversations only; previous saved history remains manageable |
| Accounting off | Usage accounting is deferred; admission quotas remain enforced |
| Semantic memory off or no Voyage key | Approved memories still use the bounded local lexical retrieval path |
| Semantic capability and user opt-in both on | Only approved memories go through the embedding worker/retriever |

AI consent, approved-memory consent, transcript persistence and external embedding
processing remain separate choices. Changing a choice never upgrades an old
temporary conversation to saved history. A persistent conversation is read-only
when saving is disabled; start a new temporary one or explicitly re-enable saving.

## Local PostgreSQL and authentication boundary

The local Compose service now includes the pinned pgvector extension used by
migration 0009 and later. For a new disposable database:

```powershell
# Repository root; do not reset an existing volume.
docker compose -f deploy/compose.local.yml up -d
docker compose -f deploy/compose.local.yml exec database createdb -U postgres moodprint_local_mvp_test
cd backend
$env:DATABASE_URL=''
$env:DATABASE_MIGRATION_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:55432/moodprint_local_mvp_test'
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Use a unique database name if it already exists; never delete existing data to
make the command work. Migration 0014 is the current application head.

PostgreSQL alone does not provide Supabase Auth. The normal application verifies
tokens through the provider and checks their `session_id` against the live
`auth.sessions` relation in its database. Pointing local PostgreSQL at hosted
Auth alone cannot satisfy this contract. A full independent local Supabase Auth
setup requires HTTPS and a shared Auth database; it is not configured here.

The supported deterministic local verification uses `tests/e2e_server.py`. It
installs a test-only provider transport while preserving the real login route,
cookie/CSRF handling, provider-token verification and database session checks.
The provider never contacts a hosted service. It supports only these public
synthetic credentials: `local-mvp-45@example.invalid` and
`local-mvp-46@example.invalid`, password `local-mvp-synthetic`.
These credentials are not accepted by the application entrypoint.

## Repeatable browser verification

Install the existing locked dependencies and Chromium as described in the root
README. Set `TEST_DATABASE_URL` to a **separate disposable loopback `*_test` DB**:

```powershell
cd backend
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:55432/moodprint_e2e_test'
uv run python ../scripts/test_fullstack.py
```

The harness refuses occupied ports and nonlocal targets, resets only that
disposable database, starts UI/API on 5174/8002 and stops its own processes.
It uses an SDK fake model and the UI explicitly labels it. This is real browser,
FastAPI and PostgreSQL verification, **not** proof of OpenAI or hosted Auth.

For manual inspection, start the same fixture with `uv run python -m
tests.e2e_server` and Vite on 5174 with
`MOODPRINT_API_PROXY=http://127.0.0.1:8002`. It also resets the named test database.
Stop these owned servers before invoking the automated harness.

## Explicitly authorized real provider smoke

After the owner authorizes the bounded calls:

```powershell
# Same disposable local TEST_DATABASE_URL, from backend.
uv run python ../scripts/verify_local_providers.py --provider-env <existing-ignored-env-file> --allow-live-openai
# Add --allow-live-voyage only if that external processing is also authorized.
```

The script reads only provider configuration from that file; it does not copy
the file, use hosted database/Auth URLs or modify it. It uses the same synthetic
Auth and local PostgreSQL as browser verification. It hard-limits the process to
8 model requests with the application's 1,200-output-token cap, and optionally
4 Voyage requests. It never automatically retries the suite. Missing credentials
or authorization remain BLOCKED rather than silently becoming fake responses.

After a partial run, `--resume` preserves the selected disposable smoke database.
Use `--model-request-limit` and `--voyage-request-limit` to restrict the **remaining**
authorized calls; starting another process does not renew the owner's budget.
The resume check exercises real semantic retrieval, edited-memory re-indexing,
revocation/deletion and one saved-context continuation. It requires the synthetic
state created by the initial run and does not replace a clean whole-suite replay.

The smoke covers five assistants, streamed validated output, explicit memory
proposal/approval, saved history after a new login and provider-visible previous
context. Optional Voyage checks index creation, real document/query embeddings
and index revocation. It is a bounded smoke, not semantic-quality calibration,
live cancellation coverage or a full re-indexing/retention audit.

Only aggregate usage and status are written to
`frontend/.cache/local-mvp/real-provider.json`. Test screenshots/traces contain
synthetic application data; provider keys never enter the browser. Do not publish
raw user environments, credentials or production session fixtures.
