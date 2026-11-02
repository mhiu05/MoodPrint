# Bounded proactive demo verification

The owner-approved demo budget is $20/day, with proactive admission yielding at
10% of the shared budget and at most two deliveries per account/day. Use one
worker with concurrency one. The budget admission/settlement checks must pass
before paid hosted testing; a spend estimate alone is not an invoice guarantee.

Keep `PROACTIVE_WORKER_ENABLED=false` until the exact-main image, complete CI,
quiet-hour dispatch/publication tests, worker health and hosted isolation checks
have passed. `PROACTIVE_ENABLED=true` exposes opt-in settings without starting
delivery. The root-owned runtime file downloaded from the existing SecureString
is the sole worker-enable authority; exporting a shell variable does not change
the container flag. Do not print `docker compose config` or the runtime file on
the host: they contain secrets.

## Hosted isolation gate

1. Install the Compose file and deployment script from the verified exact-main
   release through the existing reviewed release process. An older installed
   API/web-only Compose file cannot run the worker. Keep the accepted database
   revision at `0024_three_agent_groups`; do not downgrade the schema or roll back
   to an image whose readiness window rejects it.
2. Keep `PROACTIVE_ROLLOUT_USER_IDS` restricted to the consenting QA account(s),
   `PROACTIVE_WORKER_ENABLED=false`, `PROACTIVE_WORKER_CONCURRENCY=1`,
   `PROACTIVE_DAILY_CAP_PER_USER=2`, `PROACTIVE_BUDGET_SHARE=0.2`,
   `AI_ACCOUNTING_ENABLED=true`, and `AI_DAILY_BUDGET_USD=20`.
3. Before creating a QA schedule, read the hosted database and assert that both
   `moodprint.ai_proactive_schedules` and `moodprint.ai_proactive_jobs` are empty.
   If they are not, abort this bounded strategy. A rollout allowlist does not
   isolate scheduling: the normal tick materializes/advances all due schedules
   before authorization. Do not modify existing users' rows to make the gate pass.
4. Use the normal authenticated UI/API to opt the dedicated adult QA account into
   exactly one check-in, at a valid upcoming 15-minute time outside quiet hours.
   Leave journal context off for the first delivery. Keep the existing release
   test gate active during this bounded window so other users cannot introduce
   concurrent work. Wait for any non-QA active runs/open usage leases to settle;
   the worker also performs normal global expired-run recovery.
5. Immediately before starting the worker, read back all schedule/job owner IDs.
   Require exactly the explicitly recorded QA schedule, no non-QA rows, and no
   unresolved non-QA runs/usage. Recheck the schedule's timezone, next due time,
   versions, consent, adult eligibility, quiet hours and available budget. Abort
   if any isolation condition changed. Never force another user's schedule due.
6. Only after these gates pass, update the existing SecureString worker flag to
   true, deploy the same verified image pair through the reviewed runtime refresh,
   and verify the worker's effective boolean without printing other settings.
   Wait for the saved natural due time. Do not use `/__test/proactive/run`,
   `scripts/load_proactive.py`, synthetic auth rows, or blanket SQL updates on
   hosted production. Those helpers are for disposable test databases only.
7. Require one delivered job for the QA account/bot/slot/local date, one completed
   proactive run, only bot message parts, settled priced usage, no duplicate on
   subsequent ticks/restart, and no non-QA schedule/job changes. Check content-free
   logs for successful ticks and delivery, not heartbeat health alone: the
   heartbeat proves a successful tick within 120 seconds, not successful delivery
   of a particular job. Exercise both
   pre-dispatch cancellation and consent/schedule revocation during generation
   with separately recorded QA occurrences before expanding the cohort.
8. Disable the QA schedule through the normal API after verification. Keep the
   evidence rows for audit. Open adult rollout only after complete CI and hosted
   evidence pass and all budget/safety gates are satisfied. Existing schedules
   remain explicit opt-ins; feature availability grants no journal permission.

## Inspect service presence and liveness

These commands do not print the full environment. Run on the host as root.

```bash
compose=(docker compose --project-directory /opt/moodprint \
  -f /opt/moodprint/compose.staging.yml --env-file /opt/moodprint/staging.env)
"${compose[@]}" config --services
"${compose[@]}" ps proactive
"${compose[@]}" exec -T proactive /srv/moodprint/.venv/bin/python -m app.jobs.proactive --health
"${compose[@]}" exec -T proactive /srv/moodprint/.venv/bin/python -c \
  'from app.core.config import Settings; print("worker_enabled=" + str(Settings().proactive_worker_enabled))'
```

Deployment checks API/web and the worker when that service is declared, while
remaining compatible with an installed legacy API/web-only Compose file. A
healthy idle worker is expected when the flag is false. A worker with no successful
tick never becomes healthy; repeated tick failures stop refreshing its stamp.
Health is necessary but
does not replace successful tick/database/delivery evidence.

## Immediate worker kill switch

First stop the current process without letting a graceful shutdown finish an
in-flight delivery. This does not stop interactive API/web service.

```bash
compose=(docker compose --project-directory /opt/moodprint \
  -f /opt/moodprint/compose.staging.yml --env-file /opt/moodprint/staging.env)
"${compose[@]}" stop -t 0 proactive
```

Then persist `PROACTIVE_WORKER_ENABLED=false` in the existing SecureString via
the approved secret-safe operator path, refresh the root-owned runtime file
through the verified release deployment process, and recreate the idle worker:

```bash
"${compose[@]}" up -d --no-deps --force-recreate proactive
"${compose[@]}" exec -T proactive /srv/moodprint/.venv/bin/python -c \
  'from app.core.config import Settings; assert not Settings().proactive_worker_enabled; print("worker disabled")'
```

Do not recreate against the old runtime file before persisting/refreshing false.
Changing SSM alone does not affect running processes. Interrupted jobs keep their
leases; recovery and fencing handle them when later enabled. A message committed
before the stop remains delivered. Do not delete delivery evidence or downgrade
the database as a shutdown measure.
