# Hosted anonymous-auth compatibility (GE-01.2)

**Status: BLOCKED — no owner-approved non-production target (decision D04). Nothing hosted was contacted.**

## What exists locally

- `backend/tests/live/hosted_guard.py` refuses every hosted request unless three out-of-band variables agree: `RUN_GUEST_AUTH_COMPATIBILITY=1`, `APPROVED_GUEST_AUTH_TARGET=<20-char project ref>` and `GUEST_AUTH_TARGET_URL=https://<same ref>.supabase.co`. It never reads `.env`, never falls back to a configured/production project, and never prints the publishable key.
- `backend/tests/live/test_guest_auth_compatibility.py::test_hosted_target_guard` runs locally and proves the refusal paths (nothing approved, opt-in off, malformed/mismatched ref, non-HTTPS, foreign host). It must stay green; it is not hosted evidence.
- `test_hosted_anonymous_signup_is_verified_and_cleaned_up` is marked `live` and **skips with an explicit BLOCKED reason** without an approved target (and without a CAPTCHA token the target requires). When run against an approved target it performs one synthetic anonymous signup through the production adapter and signs out only that exact session.

## Required hosted proof that remains NOT RUN (all need D04)

| Check | Why a local fake cannot prove it |
|---|---|
| `POST /auth/v1/signup` anonymous wire contract (body shape, CAPTCHA field, `is_anonymous` in claims **and** `GET /user`) | The adapter rejects a missing flag; registered login now fails closed if the hosted token or `/user` omit `is_anonymous` (GE-01.1 risk). |
| Provider CAPTCHA enforcement and the upstream anonymous burst allowance (≥ 60 for a 50-visitor cohort) | Provider setting; changing it needs its own approval. |
| `auth.sessions` lifetime ≥ 7200 s and no other Auth/Data API/Storage/Realtime surface honouring `authenticated` for guests | Only the app deadline is enforced by this repo. |
| Guarded helpers on the hosted database: `is_provider_session_active`, `delete_guest_provider_identity`, `find_guest_orphan_subjects`, `delete_orphan_guest_identity` — grants, `SECURITY DEFINER`/empty `search_path`, anon/authenticated/service_role denial | Local grants were proven on a disposable Postgres only. |
| Child-row cascade when an anonymous `auth.users` row is deleted (identities, sessions, refresh tokens, MFA) | The local fixture models only `auth.sessions` (`ON DELETE CASCADE`). |
| TLS/cipher compatibility, provider/log/backup retention facts | Hosted facts. |

## How to run when D04 is granted (operator steps, not executed here)

```powershell
$env:RUN_GUEST_AUTH_COMPATIBILITY='1'
$env:APPROVED_GUEST_AUTH_TARGET='<approved project ref>'
$env:GUEST_AUTH_TARGET_URL='https://<approved project ref>.supabase.co'
$env:GUEST_AUTH_TARGET_PUBLISHABLE_KEY='<publishable key>'      # out of band, never committed
$env:GUEST_AUTH_TARGET_CAPTCHA_TOKEN='<one-shot token>'
uv run --locked pytest -q -m live tests/live/test_guest_auth_compatibility.py
```

Release gate G1 stays **PARTIAL** until this evidence is attached (sanitized: counts and booleans only, no tokens or identities).
