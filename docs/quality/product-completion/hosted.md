# Explicit hosted synthetic product checks

This runner is authorized only for `xhlshihobyxrgfqrdafh.supabase.co`. It is separate from the local E2E gate. It never runs migrations, changes Auth settings, sends email, starts/resets Supabase, or invokes a paid model or embedding provider. `.env` and `.gitignore` remain unchanged.

Implementation plan: validate the exact API and restricted runtime database target; prepare two synthetic confirmed Auth accounts with a durable local manifest; serve the real product with a safe lifecycle; check scoped persistence and isolation; clean only the recorded accounts through the account API. Offline guard tests cover the dangerous boundaries before any hosted execution.

Run from the repository root with its virtual environment:

```powershell
.venv/Scripts/python.exe scripts/hosted_product.py --prepare
.venv/Scripts/python.exe scripts/hosted_product.py --run
.venv/Scripts/python.exe scripts/hosted_product.py --serve
```

`--prepare` is the only account-creation step. It creates exactly two `@example.test` users with `email_confirm=true`; the admin create operation sends no email. Credentials and exact returned Auth IDs are retained only in the ignored `.local/product-completion/hosted-users.json`. Do not print, attach, commit, or copy that file into a report. Repeating prepare reuses the same complete manifest and never creates extra users. An interrupted prepare fails closed; use cleanup on the IDs already recorded and review an ambiguous interrupted network response before creating another run.

`--run` signs in those real hosted users and verifies profile persistence, a synthetic memory's creation/deletion, and the second user's inability to update it. It does not create additional accounts. It leaves the two accounts ready for browser testing.

`--serve` starts a loopback API at `http://127.0.0.1:8010` and Vite at `http://127.0.0.1:5183`. Sign in through the normal `/auth` page using the local manifest. The API verifies real hosted ES256 tokens and then admits only the manifest's exact user IDs. Storage operations reject object paths outside those synthetic owners and record original upload keys in the manifest. The browser uses the hosted publishable key; server secrets remain server-side. Local process logs stay in `.local/product-completion/`.

The seam replaces the production lifespan before it enters: no purge or reconcile loop runs, and no paid OpenAI client is constructed. Companion responses use the existing deterministic `ScriptedModel` scenarios and the existing in-process fake Responses transport for analysis/coach replies. SDK tracing is disabled. This can verify product wiring and persistence only; it is not evidence of live model quality or paid-provider reliability.

Knowledge remains configured as `pgvector`; its actual adapter is constructed when a Voyage key exists. A guard prevents every search from reaching paid query embedding. It checks only the existence of `knowledge.corpus_versions` through `pg_catalog.pg_class`/`pg_namespace` and reports an explicit missing-schema or paid-retrieval-disabled error. It never replaces retrieval with a fixture, hash embedding, seed corpus, or invented result. Knowledge metadata routes use the actual hosted database and may fail if the schema is absent.

`GET http://127.0.0.1:8010/hosted-product/preflight` checks only these known relation names through `pg_catalog.pg_class`/`pg_namespace`: the profile, case, evidence, plan and memory tables; phase 3 proposal/analysis/roleplay/attachment/assessment tables; knowledge corpus versions; and agent sessions. It reads no user rows and needs no schema usage grant. Missing phase 3/knowledge relations block their corresponding journeys without blocking the independent foundation workflows. Deploying the missing migrations is a separate owner-authorized task.

Individual `DELETE /v1/cases/{id}` is blocked in this seam because the product route invokes a global evidence purge after deletion. The account cleanup API uses the scoped service directly and remains available.

With `--serve` running, standalone browser acceptance reuses only the manifest accounts:

```powershell
cd frontend
node scripts/hosted-product.mjs
```

It checks login validation, case draft/edit/timeline/evidence/plan persistence, support/profile flows, and A/B API isolation. It blocks browser requests outside the exact local/hosted origins and blocks all signup/OTP/recovery/invitation operations. Only two meaningful desktop/mobile screenshots and a nonsecret resource/check receipt are saved under `.local/product-completion/`; prior receipts are archived on repeat runs. A missing genuine expired-token fixture is recorded as unexecuted rather than passed. The browser suite does not create or delete users, deploy missing schemas, or enable paid models.

After browser work, stop `--serve` with Ctrl+C, then run:

```powershell
.venv/Scripts/python.exe scripts/hosted_product.py --cleanup
```

Cleanup checks only each exact recorded Auth ID, signs in as that account, and invokes `DELETE /v1/me` with `confirm=DELETE`. The product's account-deletion code removes only that synthetic owner's cases, evidence, conversations, derived Storage objects, and Auth user. It never lists Auth users, scans another owner, lists a Storage bucket, runs broad SQL deletion, or enters global maintenance. The manifest is retained as a local receipt with per-user deleted flags. Failures retain the manifest and fail closed; unresolved active agent runs may need cancellation through the product before retrying account deletion. Do not remove the manifest before cleanup succeeds.

Offline verification (does not access Supabase):

```powershell
.venv/Scripts/python.exe -m pytest scripts/tests/test_hosted_product.py scripts/tests/test_e2e_stack.py -q
.venv/Scripts/python.exe -m ruff check scripts/hosted_product.py scripts/hosted_product_app.py scripts/tests/test_hosted_product.py
```

Supabase references: [admin user creation](https://supabase.com/docs/reference/python/auth-admin-createuser) documents email confirmation and no email delivery; [changelog](https://supabase.com/changelog) was checked for relevant Auth/HTTP changes. No CLI or project configuration changes are required.
