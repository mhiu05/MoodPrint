# Separate PR proposal: explicit conversation-scoped evidence reuse

Status: **DESIGN ONLY — disabled in this implementation**. No grant, snapshot table,
reuse policy stamp, migration or UI switch is shipped here. Per-turn authorization
and F03's conservative context projection remain the default and the enforced policy.

The proposed feature would let a user authorize discussion of one verified mood
snapshot in one Nhịp conversation for a visible, short lifetime. It would not
authorize wider queries, long-term memory, a different bot, different date range,
another conversation, or restoration of old assistant claims as evidence.

| Permission | Current implementation | Proposed separate feature |
|---|---|---|
| Query scores | Explicit `moodScope` on this HTTP turn | Same per-turn query permission |
| Discuss verified snapshot | Only the current run, until termination/expiry | Separate, visible, revocable grant |
| Read saved chat | Existing owner/history permission | Never grants source reuse |
| Use assistant history as evidence | Forbidden | Still forbidden |
| Store a memory | Separate proposal and user confirmation | Unchanged; no automatic conversion |

Proposed consent UI: an unchecked choice naming the selected dates, Nhịp, the
current conversation, and a concrete expiry (for example, 15 minutes). Show an
active-grant indicator and a prominent revoke action. Expiry is a privacy lifetime,
not an analytical sufficiency threshold. Browser reload or saving history must
not silently extend it. Changing dates requires a new explicit choice. Chat prose,
successful earlier analysis, absence of an opt-out, and a re-share button are not
reuse authorization.

A server-authoritative grant would bind owner, conversation, bot, evidence ID,
source revisions, monotonic data/consent versions, authorized range, issued time,
expiry, and revocation version. Before *every* provider call and final emission,
revalidate the grant and live source versions. A mood edit/deletion, AI withdrawal,
account deletion, grant revocation or expiry invalidates the snapshot and all
derived context. Regrant creates a new grant; it cannot resurrect old evidence.
An inaccessible/unavailable source must fail closed, with a different state from
a successful read returning zero records. Mixed-worker operation cannot rely on
RAM or a browser flag for revocation.

Persistence needs a separately reviewed migration and a minimal retention
contract. Prefer revalidatable references and deterministic statistics over raw
tool traces or notes. If a snapshot must contain scores, justify every retained
field and its deletion/expiry sweep. Never store private mood notes. A grant must
have a unique identity, owner/conversation authorization, bounded cardinality,
expiry cleanup and an audit trail containing no mood content. Source changes
must invalidate even after a worker restart, backup restoration or new session.

F03's current `text-v1`/`mood-turn-v1` stamps cannot prove these new conditions.
Do not reinterpret or backfill them. A new policy stamp and reconstruction rule
would need explicit provenance and an authoritative valid-grant check. Legacy
NULL stamps stay untrusted. Stage the migration before the new binary; reject
mixed old workers that could replay unfiltered context. Rollback revokes reuse
and preserves the F03 cutoff, rather than restoring unfiltered history.

Required verification before enabling a separate PR:

- Real PostgreSQL migrations, constraints, least-privilege access and source/grant
  invalidation; legacy transcript and RLS/ACL preservation; no trusted backfill.
- Owner/bot/conversation/range isolation; expiry boundaries; revoke/regrant;
  concurrent edit/revoke during a tool call, model call and buffered SSE final.
- Saved conversation, pagination cutoff, worker/process restart, second worker,
  new session, restoration and cleanup races; loss of authoritative storage.
- Actual SDK input captures proving revoked source *derivatives*, including user
  copies, are excluded across boundaries without widening the context budget.
- Desktop/mobile/keyboard consent and revoke UX, and matched real-model evaluation
  with per-turn-only behavior as the frozen control.

None of this migration/reuse contract has been verified here. Keep the feature
off until that separate implementation and its privacy tests are reviewed.
