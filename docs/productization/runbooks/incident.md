# Incident runbook

Audience: whoever is on call for the MoodPrint beta (operator / product owner).
Alarm definitions: `deploy/aws/cloudwatch-alarms.json` (configuration only until AWS staging
exists). Log group: `/moodprint/staging/containers`, retained 30 days. Logs are content-free
(`metric=<name> …` lines, error classes, request ids); never paste user content into tickets.

## 1. Severity

| Level | Examples | Response |
|---|---|---|
| SEV1 | Data exposed to the wrong user; app down; credentials leaked | Act now; stop the bleeding first |
| SEV2 | One feature broken for everyone (chat, matching, activities, AI); alarms firing persistently | Same day |
| SEV3 | Degraded latency, a single user affected, noisy alarm | Next working day |

## 2. First five minutes

1. Acknowledge the alarm and note the time (Asia/Bangkok) in the incident log.
2. Check `GET /api/v1/health/live` and `/api/v1/health/ready`.
3. Check the alarm's metric over the last hour in CloudWatch, then the Logs Insights queries below.
4. Decide: turn a feature off (fastest), roll back the image, or keep investigating.

## 3. Fast switches (env + redeploy, no code change)

| Problem | Switch |
|---|---|
| Activities misbehaving | `ACTIVITIES_ENABLED=false` or narrow `ACTIVITY_KINDS` |
| Matching v2 complaints | `MATCHING_SCORER=v1` |
| AI cost spike / provider failure | `AI_DAILY_BUDGET_USD` lower, `AI_DAILY_TURNS_PER_USER` lower, or AI feature flag off |
| Moderation screen faulty | `MODERATION_ADMIN_ENABLED=false` (existing restrictions stay in force) |
| Bad release | Redeploy the previous image digest ([11](../11-migration-and-rollback.md)); schema stays |

## 4. Alarm playbooks

- **Http5xxCount** — Logs Insights:
  `fields @message | filter @message like /request_failed|metric=http_5xx/ | stats count() by bin(1m)`.
  Error classes come from `request_failed error_type=…`. Compute the ratio with:
  `filter @message like /metric=http_requests|metric=http_5xx/ | parse @message /metric=http_requests value=(?<n>\d+)/ | stats sum(n) as requests, sum(strcontains(@message, "metric=http_5xx")) as errors by bin(5m)`.
  Beta threshold for action: errors / requests > 2 % over 5 minutes.
- **ReadinessFailing** — database unreachable or schema revision not in `READY_REVISIONS`. Check the
  Supabase status page and the last migration. Do not run migrations to "fix" readiness without the
  reviewed apply path.
- **AiRunFailedRate** — provider outage or quota. Check `ai_terminal_retry` lines; lower AI limits or
  turn AI off; users see an honest retry message, drafts are preserved.
- **AiBudget80** — spend reached 80 % of the daily ceiling; new runs stop at 100 % (503
  `AI_BUDGET_EXHAUSTED`). Decide whether to raise the ceiling; never remove it during the beta.
- **DiskUsed80** — Docker logs or images filling the root volume: `docker system df`, prune old
  images (keep the previous release digest for rollback).

## 5. Privacy or safety incident (SEV1)

1. Contain: disable the affected feature with its flag; for a leaked secret, rotate it first.
2. Preserve evidence: take a database dump (backup runbook §4.2) before cleaning anything.
3. Do not contact users outside the app. Escalation contacts are in the moderation runbook §5
   (**owner input required, Q-03**).
4. Assess what data, which users, which period. Notification duties under Vietnamese personal-data
   rules (Decree 13/2023) are a legal decision — **owner/legal input required** before the beta.

## 6. After the incident

Write a short blameless note: timeline, impact, root cause, what fixed it, follow-ups with owners.
Add a regression test for the cause where possible.
