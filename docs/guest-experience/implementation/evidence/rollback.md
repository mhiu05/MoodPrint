# Guest-aware rollback and restore

Status: procedure prepared; no hosted operation authorized or executed.

Use only an image that understands immutable guest lifetimes, the guest-aware Auth helper and **0018_app_feedback**. Keep `READY_REVISIONS` strict. The registered-only image from the original main is incompatible even when new entry is off. Never downgrade the database, remove guest columns, reset deadlines, refund uncertain work or stop cleanup.

1. Disable entry, paid dispatch, collection/review and interactive guidance independently. Existing denial at T, purge, orphan reconciliation, feedback retention and conservative settlement must continue.
2. Drain admitted requests and streams within their deadlines. Preserve detached liability. Deploy only a reviewed guest-aware compatible image, or retain a maintained denial/cleanup service until zero guest/attempt/reservation obligations remain. This document does not authorize deployment.
3. Verify schema/head/helper/readiness, expired-session 401, private-output suppression, worker progress, registered canary and liability before traffic. Never accept an older schema head merely to make readiness green.
4. Monitor content-free cleanup lag/retry/incident/orphan counts, admission refusals, uncertain/overrun liability, pool wait/RSS/SSE/500s. An authorization bypass, >5 minute cleanup lag or ambiguous orphan >24 hours closes entry/paid work and escalates while denial/cleanup remain active.

Restore into quarantine without a public listener. Preserve T0/T and current database time; apply revocations/deletions, reconcile attempts without another signup, settle uncertain reservations, purge guests and enforce feedback retention/reviewed redactions. Verify zero expired references and an unchanged registered canary before lifting quarantine. Provider/log/backup deletion facts remain separate D01/D03 gates.

The [local rehearsal](capacity-recovery.md) physically restores a synthetic dump taken before T after T has passed. Test helpers are absent from the production entrypoint. Production restore requires separate target-specific approval.

The admission HMAC has no live rotation protocol. Keep it stable. For planned rotation, close entry and collection, wait at least the longest durable admission/orphan window (24 hours), resolve attempts and review counter behavior. Changing the key does not preserve old keyed counters.
# Publication hold during source integration

Keep `deploy/guest-experience.release-hold` tracked through merge and rollback.
Both automatic and manual publication honor it; no exact-main staging release
is produced for the deployment poller. Do not remove the marker to validate a
merge or relax schema0018 readiness. A separate owner-approved release change
must resolve hosted/schema/decision/manual prerequisites before removal.

