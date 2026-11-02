# MVP demo runtime

The owner approved a temporary $20/day maximum for MoodPrint AI on 2026-11-02.
Enable demo rollout only after the complete exact-main CI/release and hosted QA.
The application remains on `0024_three_agent_groups`; these safeguards add no
database migration. Keep the existing immutable release and attestation checks.

## Runtime settings

Use the existing `/moodprint/staging/runtime` SecureString. Never print its value
or the full rendered Compose configuration.

```dotenv
AI_ENABLED=true
AI_ACCOUNTING_ENABLED=true
CHAT_HISTORY_ENABLED=true
AI_MULTI_MESSAGE_ENABLED=true
AI_THREE_AGENT_EXPERIENCE_ENABLED=true
AI_SMART_ORCHESTRATION_ENABLED=true
AI_GROUP_CHAT_ENABLED=true
AI_DAILY_BUDGET_USD=20
AI_GLOBAL_CONCURRENCY=10
AI_USER_CONCURRENCY=2
AI_TIMEOUT_SECONDS=60
AI_ORCHESTRATION_PLANNER_TIMEOUT_SECONDS=15
PROACTIVE_ENABLED=true
PROACTIVE_WORKER_ENABLED=false
PROACTIVE_WORKER_CONCURRENCY=1
PROACTIVE_DAILY_CAP_PER_USER=2
PROACTIVE_BUDGET_SHARE=0.2
DATABASE_POOL_SIZE=5
DATABASE_POOL_OVERFLOW=2
GUEST_AUTH_ENABLED=false
GUEST_PAID_ENABLED=false
GUEST_SEMANTIC_ENABLED=false
STT_ENABLED=false
SEMANTIC_MEMORY_ENABLED=false
```

During QA, `AI_V3_ROLLOUT_USER_IDS` and `PROACTIVE_ROLLOUT_USER_IDS` contain only
the authorized **application** user UUIDs, not their Supabase Auth subjects.
After hosted verification, empty lists open availability to the existing adult
account gates. Availability does not enable schedules or journal sharing: users
must opt in, and existing consent/version checks remain mandatory. Guests do not
get group chat, sharing or proactive delivery. Public visitors cannot access
private journal routes.

The worker flag becomes true only after the
[isolated hosted worker checks](proactive-qa.md) pass. Keep one worker with
concurrency one. The initial two-per-day limit permits one morning and one
evening check-in; quiet hours are rechecked before dispatch and publication.

## Financial admission

`AI_DAILY_BUDGET_USD` is enforced using a conservative liability ledger, rather
than only looking at usage after requests finish. Every priced AI usage row
reserves $2 before dispatch under the same PostgreSQL advisory lock. This covers
at most three model requests, each bounded by the supported Luna input window
and the application's 1,200-token output ceiling. All child runs reserve too.
Open or uncertain usage keeps its reservation; only complete priced terminal
usage releases unused liability. Unknown models or historical usage fail closed.
Account deletion cannot refund that day's dispatched work. Midnight handling
also carries the previous day's ledger, conservatively reducing available funds.

The known model is `gpt-6-luna`. Conservative rates include long-context,
cache-write, regional and Fast premiums. The resulting maximum liability is
below the $2 reservation. Sources:
[model limits and premiums](https://developers.openai.com/api/docs/models/gpt-6-luna),
[base pricing changelog](https://developers.openai.com/api/docs/changelog).
Keep model changes behind a new pricing/bounds review.

With share `0.2`, proactive reservation is refused when total AI liability plus
that new reservation would exceed $4. Interactive chat can continue up to $20.
This is deliberately conservative and may stop proactive delivery early; it
cannot reserve the interactive share. Keep guest paid calls, voice and embeddings
off because they use separate accounting paths. A shared provider key used by
other applications is outside this ledger. This application limit is not a
claim about taxes, changing provider prices or unrelated provider-account usage.

## Guest prerequisites

Guest entry stays disabled while the CAPTCHA site key/provider configuration is
missing. Do not substitute a test CAPTCHA key or bypass verification for the demo.
Registered adult accounts remain the supported demo route. Before enabling guest
entry later, verify the actual anonymous provider flow, CAPTCHA origin/CSP,
expiry/cleanup and the desired guest journal policy. Existing authenticated guest
trials historically permit their own journal data; they must not be mistaken for
registered-account login when evaluating a stricter guest privacy requirement.

## End the demo or stop delivery

For immediate delivery shutdown, first stop only the worker without a graceful
in-flight send, then persist `PROACTIVE_WORKER_ENABLED=false` and refresh the
runtime using the verified release. See the
[kill-switch procedure](proactive-qa.md#immediate-worker-kill-switch).
Set `PROACTIVE_ENABLED=false` to close proactive opt-in settings as well.
To close all paid chat, use `AI_ENABLED=false`; keep accounting and settlement
intact. Restore rollout allowlists and the approved post-event budget through
the same SecureString path. Never erase accounting to reset the cap.
