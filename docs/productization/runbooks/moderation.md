# Moderation runbook (beta)

Audience: MoodPrint staff with a `moderator` or `admin` row in `moodprint.staff_roles`.
Screen: `/#/admin/reports` (visible only when the session reports `staff`). API: `/api/v1/admin/*`
(see [07 §3.4](../07-database-and-api-contracts.md#34-moderation-i)).

## 0. Preconditions

- `MODERATION_ADMIN_ENABLED=true` on the deployment. When false every admin route returns 404.
- Staff must have signed in within the last 12 hours (`REAUTH_REQUIRED` otherwise — sign out and in).
- Roles are granted by an operator with database access. `scripts/grant_staff_role.py` is for local
  and `*_test` databases only and refuses other URLs; a hosted grant is a reviewed SQL change.

## 1. Service level

- Triage every report within **48 hours** of `createdAt` during beta.
- Check the queue at least twice a day (morning and evening, Asia/Bangkok).
- Emergency content (self-harm, threats of violence, a minor at risk) skips the queue order — see §5.

## 2. Triage steps

1. Open the queue ("Đang chờ"). Oldest reports first.
2. Press **Nhận xử lý** to claim. The report moves to `in_review`; a second moderator sees the new
   status and a stale action returns `REPORT_CHANGED`. Reload and re-read before deciding.
3. Read only the evidence the reporter selected (up to two messages and two activity answers). The
   screen never shows emails or user ids; `subjectRef` is an opaque reference stable per report.
   `priorActions` counts earlier decisions about the same subject.
4. Decide using §3. Write a short internal note (never shown to users; no copied message text
   beyond what is needed). Confirm in the dialog.

## 3. Action guidelines

| Situation | Action | Duration |
|---|---|---|
| No rule broken, misunderstanding, disagreement | **Bỏ qua** (`dismiss`) | — |
| First mild breach: rudeness, unwanted flirting stopped after one ask, sharing contact details pushily | **Cảnh báo** (`warn`) — subject sees a session notice | — |
| Repeated breach after a warning, harassment, sexual content, hate speech | **Hạn chế kết nối** (`restrict`) — removed from discovery, rooms closed, activities aborted | 7 days (first), 30 days (repeat) |
| Threats, doxxing, scams, solicitation, minors targeted, evasion of a restriction | **Tạm khóa tài khoản** (`suspend`) — sessions revoked, sign-in refused | 30–90 days |

- Prefer the least severe action that stops the harm. When unsure between two rows, choose the
  lighter one and note why.
- `priorActions ≥ 2` with a new confirmed breach → at least `restrict` for 30 days.
- Lifting early (`POST /admin/users/{ref}/lift`) is **admin only** and must be noted in the audit
  log by the admin with the reason.

## 4. What users see

- Reporter: status text via `GET /reports/{id}` (received / in review / resolved). No outcome detail.
- Subject (warn): "Tài khoản của bạn đã nhận một cảnh báo về quy tắc cộng đồng" until dismissed.
- Subject (restrict): a notice with the end date; matching, requests, messages and invites return
  `SOCIAL_RESTRICTED`.
- Subject (suspend): sign-in returns `ACCOUNT_SUSPENDED`; open streams receive `access_revoked`.

## 5. Escalation and emergencies

> **Owner input required (Q-03).** Contacts below are placeholders until the product owner fills them.

| Case | Contact | Channel |
|---|---|---|
| Imminent self-harm or threat to life | _TBD (Q-03)_ — and advise the user to call 115 / 113 | _TBD_ |
| Child safety | _TBD (Q-03)_ | _TBD_ |
| Legal request / law enforcement | _TBD (Q-03)_ | _TBD_ |
| Moderator disagreement, appeal | Product owner _TBD_ | _TBD_ |

Do not contact users outside the app. Do not export or screenshot evidence outside the admin
screen unless legal escalation requires it, and record that in the internal note.

## 6. Audit and retention

- Every decision writes a `moderation_actions` row (actor, action, note, until) and a content-free
  log line `metric=moderation_action action=<action>`.
- Reports and moderation actions are purged after 1 year by the retention job.

## 7. Turning moderation off

Set `MODERATION_ADMIN_ENABLED=false` and redeploy. Existing restrictions and suspensions stay in
force (they are columns on `users`); lifting them then requires a reviewed SQL change.
