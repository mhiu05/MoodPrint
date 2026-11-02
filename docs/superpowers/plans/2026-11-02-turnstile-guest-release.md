# Turnstile and Guest demo release

Owner approved the real Turnstile site key `0x4AAAAAAFwi8Fwa_Gv_O6n3` for
`moodprint.duckdns.org`; Supabase project `roznanxbiyqybjpvtilq` has CAPTCHA and
anonymous signup enabled. Secret stays in Supabase. Continue branch `test/11-2`.

## Required behavior

- Registered password login, signup, recovery, resend and password step-up carry
  one fresh CAPTCHA response using `gotrue_meta_security.captcha_token` at the
  provider boundary. Missing required token fails before provider I/O. Existing
  CSRF, cookie, session, rate and eligibility checks remain. Password update and
  refresh-token grant stay CAPTCHA-exempt where the upstream contract says so.
- Share the existing explicit Turnstile implementation. Expiry/error resets the
  response without clearing form data; new attempts never reuse consumed tokens.
- Guest entry remains an explicit 18+ two-hour trial. Preserve attempt idempotency,
  exact expiry, cleanup, private-owner isolation and Matching denial.
- Guest AI uses verified conservative Luna pricing, 50 turns, one concurrent turn
  per guest and two guest turns globally. Its $5/day sublimit is INCLUDED in the
  global $20/day conservative liability cap. Voice/embeddings stay disabled.
- No schema migration, `.gitignore` change or CI refactor. Deploy only the exact
  verified main SHA with unchanged release identity/digests/attestations.

## Implementation and validation

1. Backend Auth: optional repr-hidden captchaToken DTOs, requirement flag, public
   requirement discovery, exact GoTrue payload, safe errors and wire-level tests.
2. Frontend: shared challenge hook/component, normal Auth+reauth+Guest entry,
   token lifecycle and form preservation tests at desktop/mobile.
3. Guest financial admission: detached guest liabilities count toward global cap
   without double counting live usage; serialized admission and purge survival.
4. Deployment: runtime Auth/Guest flags derive only the fixed Cloudflare origin
   for the proxy CSP; never copy arbitrary origins/secrets into the web service.
5. Full local unit/API/Postgres/browser/fullstack and remote CI. Review, commit by
   function, push current PR34, merge only after green; require main push CI and
   verified release before deployment.
6. Hosted real challenge, registered+guest session, refresh/logout, AI/quota,
   denial/expiry/cleanup/idempotency and worker opt-in evidence. Keep an accurate
   report of live email/provider/expiry checks that cannot be established.

Official wire reference: [Supabase Auth OpenAPI](https://raw.githubusercontent.com/supabase/auth/master/openapi.yaml).
Model/pricing bounds: [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [pricing changelog](https://developers.openai.com/api/docs/changelog).
