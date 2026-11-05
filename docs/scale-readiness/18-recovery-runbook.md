# Recovery policy and executable rehearsal

Decision date: 2026-11-05. **Select a 24-hour RPO and an 8-hour RTO planning target**
for a single project/instance failure, once access to a healthy recovery region and
backup keys is available. Neither target has been achieved on hosted infrastructure.
Regional/account loss is outside this initial target; it requires a separately costed
copy and access-recovery plan. Keep the release recovery gate open.

The 8 hours allow 1 hour to declare/fence, 3 hours to restore DB/objects/host,
2 hours for secrets/config/security/financial reconciliation, and 2 hours for application
verification and controlled cutover. These are budgets for a measured rehearsal, not
provider restore-time promises. Escalate immediately when a phase exceeds its budget.

## What the actual inventory supports

| Domain | Evidence observed in this workspace | Missing proof |
|---|---|---|
| Supabase database | Project fingerprint `44a655e04517`, Pro, Tokyo, PostgreSQL 17.11; approximately 18.2 MB at the earlier read | Actual backup list, latest successful capture, physical-backup eligibility/PITR state and restore success |
| Supabase private Storage | `journal-media`, private; 6 objects, metadata total 9,473,860 bytes | Object bytes, full private inventory/checksums and restore with correct ownership/policies |
| EC2/EBS | Staging Sydney, `m7i-flex.large` running, encrypted 30 GiB gp3; current target-volume query returned zero snapshots | Scheduled backups, retained snapshot availability, KMS decrypt permission and boot from a recovered volume |
| Configuration/secrets | SSM `/moodprint/staging/runtime` version 26 was observed | Independent encrypted recovery copy, current deployment digest, complete consumer mapping and break-glass access |

Sources: [redacted inventory](13-cloud-inventory-redacted.md),
[AWS inventory](evidence/aws-inventory.json),
[Storage aggregate](evidence/supabase-storage-grants.json). No new hosted backup or
object download was performed in this round. A Pro subscription alone does not prove
that this project's latest backup exists or meets the RPO.

## Selected policy

| Domain | Capture and retention | Verification and failure response |
|---|---|---|
| Database | Retain the included Pro daily backups, accessible for 7 days. Add an independent encrypted logical export every 12 hours after approving the destination/job; retain 14 twelve-hour versions (7 days) and 4 weekly versions | Record capture start/end, project fingerprint, schema/migration head, dump format/client version, counts and SHA256; restore monthly and before a risky deployment. An expired/failed run is a failed recovery gate |
| Private objects | Copy every object byte plus private key/owner/MIME/size/checksum inventory to an independent encrypted, access-controlled destination every 12 hours; same version retention as logical DB exports | Paginate the full bucket, compare enumerated counts and every checksum, retry failures. Keep immutable generations; a mirror that propagates deletes is insufficient |
| EC2/EBS | Daily encrypted snapshot, 7 successful daily versions, plus a prechange snapshot retained through the rollback window | Wait for `completed`, verify exact volume/account/region/KMS mapping and access, then restore to a NEW volume/instance. A receipt JSON is not an EBS backup |
| Config/images | Capture at every approved release/config change and every 12 hours; retain with the matching DB/object generation and compatible image digest | Include Compose/proxy/worker config, image digests, schema compatibility, SSM parameter names/versions, IAM/profile/network/DNS settings and rebuild steps; test rebuilding an isolated host |
| Secrets/keys | Encrypted independent vault export at every rotation and every 12 hours, with the same bounded retention; record only vault item/version references in ordinary evidence | Test recovery access from a separate operator session. Include DB/custom-role passwords, application signing/HMAC/encryption keys, provider/SMTP credentials and KMS/vault recovery authority; rotate the previously exposed DB credential through the coordinated C01 process |

The 12-hour independent jobs provide retry headroom for a 24-hour target. Alert on a
failed run immediately and on the oldest required component reaching 18 hours; page
the recovery owner before 24 hours. Until a working monitor and timely complete
generation exist, RPO remains **UNPROVEN**. Pro daily backups remain useful but do
not replace the independent project-deletion recovery copy. Do not enable paid PITR
for this initial 24-hour policy. Reconsider PITR if acceptable data loss becomes smaller.

Retain only authorized user data, in the approved residency/access boundary. Apply
deletion requests and consent changes again before recovered data is exposed; maintain
the deletion/revocation record independently of the rollback point. Keep backup keys
and break-glass recovery instructions outside the account/project being recovered.

Database backups contain Storage metadata, **not object bytes**, and omit custom-role
passwords. EBS snapshots contain on-volume blocks, not external SSM state, provider
configuration or a Supabase database. Capture filesystem writes consistently: drain
applications and flush/quiesce writes; a root-volume snapshot may require an approved
instance stop. Select the common recoverable point across DB and object versions;
do not simply combine their newest files. Independently timed captures do not prove
cross-system consistency; use a fenced capture window or reconcile every DB object
reference to the corresponding retained object version.

Costs remain unquoted: independent storage, export/download egress, requests, snapshot
retention, restored EBS/EC2, and a temporary Supabase project can incur charges. Obtain
the destination/region-specific estimate and exact retention/job proposal before cloud
activation. No paid services or cloud mutation were created here.

## Offline artifact verification

From the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/verify_recovery.py --manifest X:/recovery-vault/generation/manifest.json
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_recovery_verification.py -q
```

Use an access-controlled mounted/decrypted view of the encrypted backup generation,
outside this repository. No real backups, `.env`, private object paths or secret values
belong in committed evidence. The verifier never connects to a network, extracts an
archive, imports SQL, reads runtime configuration automatically or modifies an artifact.
It streams SHA256 and prints only safe categories, ages and aggregate counts.

Input JSON has `schema_version: 1` and `components` containing **all five** keys:
`database`, `storage`, `configuration`, `secrets`, `infrastructure`. Each value has
`captured_at` (timezone-aware ISO8601 capture time) and `artifacts`, an array of
`{ "path": "relative-file", "size_bytes": 123, "sha256": "64-lowercase-hex-digits" }`.
Paths resolve under the manifest directory; traversal, absolute paths, escaped symlinks,
duplicates and empty non-Storage artifacts fail. Storage must also have
`expected_objects` equal to the full source inventory's object count, with one artifact
per object. Zero objects must be explicit; zero-byte Storage objects are valid.
Store the full private object-key/version/owner inventory alongside this protected
generation; the public report does not print it. Hash the infrastructure receipt file
containing actual snapshot IDs, status, timestamps and KMS references; separately
read back those cloud objects through the authenticated provider API.

Exit 0 means `ARTIFACT_INTEGRITY_PASS` against the supplied manifest within 24 hours.
Exit 1 means incomplete, stale, corrupt or malformed evidence. `--now <ISO8601>` exists
only for reproducible fixture/testing checks; use the actual clock for operations.
All success reports say `restore_proven=false`, `source_completeness=NOT_PROVEN` and
`cloud_resources_verified=false`. A self-authored manifest cannot authenticate its
own source, prove that encryption keys work, validate archive SQL, or prove a usable
snapshot. Protect the manifest's provenance independently. Do not close a restore gate
based only on this script.

## Local rehearsal already executed

```powershell
backend/.venv/Scripts/python.exe scripts/rehearse_recovery.py --run-synthetic --output docs/scale-readiness/evidence/round2-recovery-rehearsal.json
```

The output file must be new; the script refuses to overwrite evidence. For a new run,
choose a new evidence filename. It uses locally present `postgres:17.11` with
`--pull=never`, a fresh UUID name/ownership label, `--network none`, no published ports,
1 CPU/512 MiB limit and tmpfs database storage. It accepts no existing container ID,
database URL, project ID or credentials. It never uses the team's shared disposable DB.

Observed [rehearsal evidence](evidence/round2-recovery-rehearsal.json): custom-format
`pg_dump` to a new database with `pg_restore --exit-on-error --single-transaction`;
2 synthetic rows recovered; RLS kept the other owner's row hidden; the synthetic
`uncertain` financial hold retained its 120,000-micro liability. Two synthetic private
object byte sequences and synthetic config/secret files were copied back and compared.
All five manifest domains passed integrity checks. Elapsed local time was 3.812 seconds.
Cleanup verified the UUID ownership label, network isolation and tmpfs before removing
the one created container, then confirmed no container with that run label remained.

This is a small synthetic mechanism rehearsal. It does not exercise MoodPrint's whole
schema, Supabase Auth/Storage, actual encryption/vault recovery, EBS boot, live access,
provider downtime, production-sized data or hosted RPO/RTO. The local infrastructure
receipt is explicitly synthetic and contains no real snapshot. The PostgreSQL image
tag is not an immutable digest pin; record/pin the reviewed digest for a release drill.

## Hosted recovery: exact operator sequence, not executed

1. Record incident/restore-start time and affected source fingerprints. Verify account,
   project, environment and backup date independently. Designate incident owner and
   a second verifier. Fence API writes, all workers/cron/webhooks and generation/email
   dispatch; record outstanding/uncertain liabilities. Keep unaffected data available
   only where consistency allows. Do not refund uncertain holds or replay provider calls.
2. Read Supabase Database > Backups for this exact Pro project. Record all successful
   backup timestamps, physical/logical format and PITR state without tokens or URLs.
   Compare the newest usable **capture**, not the download time, to the incident point.
   Read the target EBS volume's completed snapshots and KMS access. Verify the vault's
   independent DB/object/config/secret generation. If anything is absent, stop and
   declare the corresponding domain unrecoverable; do not substitute a receipt.
3. Before provisioning, approve the exact temporary project/instance/volume names,
   region, network fencing, backup-generation identifiers, access principals, cost cap,
   maintenance window and cleanup owner. Source data/instances stay untouched.
   Never restore a daily backup over the source just to test it.
4. Prefer a logical restore into an isolated target where outbound work can be disabled
   before data is activated. Pin compatible PostgreSQL/Supabase tooling; run
   `supabase --version`, `supabase db dump --help` and restore-tool `--help` first.
   The November 2026 CLI v3 defaults to local targets and changes remote selection;
   explicitly resolve and review the actual target before any export/import. Use
   secure password input or an access-restricted passfile; keep credentials out of
   process arguments/logs. Include application/auth data, roles/grants/RLS, necessary
   extensions and migration history. Use the current Supabase logical-restore procedure
   for managed schemas; plain generic PostgreSQL restore flags are only the local fixture.
5. If choosing Dashboard **Restore to a new project**, review its displayed cost and
   restrictions before confirming. Physical clones can start copied cron/webhook/other
   external extensions immediately. Do not run that path until their side effects are
   inventoried and controlled. It copies the database and encryption root key; Storage
   objects/settings, API keys/Auth settings and other service settings need separate
   work. For a manual logical restore, arrange secure recovery of the encryption root
   key before claiming Vault/encrypted-column readability. Do not print key material.
6. Restore the matching private object bytes through the supported Storage API into
   the isolated target; verify every inventory entry, checksum, MIME and size. Apply
   private bucket settings and RLS/ownership deliberately: copying/uploading as an
   administrator can change owner metadata. Check owner A/B and anonymous access;
   compare application journal references to object generations and identify orphans.
   Never make the bucket public to get a smoke test to pass.
7. Restore EBS to a NEW volume in the recovery instance's Availability Zone; verify the
   encryption key is usable. Rebuild or boot a separately approved isolated host with
   the compatible image digest and reviewed Compose/proxy/process config. Recover
   runtime configuration/secrets from the independent vault, rebind project-specific
   URLs/keys, reset omitted custom-role passwords, and validate least privilege.
   Disable email and paid-provider dispatch until controlled canaries are approved.
8. Verify migration head, constraints, RLS/grants, row counts/checksums, deleted-user
   and consent state; compare all financial holds/unknown calls with the incident
   record and provider receipts. Run user A/B cross-access, confirmed login/session,
   private journal upload/download, no-resurrection deletion, read/cancel and approved
   chat smoke tests. Check drain/worker fencing before admitting any new work.
   Reapply deletions/revocations that happened after the chosen backup point.
9. Record the common recovered timestamp, actual lost interval, phase timestamps,
   restore-end/application-ready time, failed checks and cost. Close RPO only if all
   required domains reconcile to a common point no older than 24 hours; close RTO
   only if the application-ready time is within 8 hours of incident declaration.
   Otherwise record the miss and update sizing/procedure; do not infer it from DB size.
10. Approve a separate reviewed cutover after the target passes. Keep source and
    previous compatible deployment available until acceptance; rollback routes to the
    previous healthy system only if data/financial consistency permits. Do not blindly
    merge divergent writes. Fence/remove only individually identified rehearsal
    resources after evidence retention; never bulk-delete snapshots or user databases.

Activation remains the concrete C06 cloud proposal: independent destination and its
encryption/access policy, 12-hour exports/object/vault jobs, 7-day/4-week retention,
daily EBS snapshots and notification channel, plus one separately fenced/costed hosted
restore. RPO/RTO choices are made here; cloud implementation and proof remain open.

## Current primary documentation

Checked 2026-11-05. Supabase's markdown changelog fetch was unsupported by the web
reader; the HTML changelog was read, including the November 4 CLI v3 breaking change.

- [Supabase database backups](https://supabase.com/docs/guides/platform/backups): Pro daily retention, Storage/password exclusions, downtime and PITR behavior.
- [Supabase CLI changelog](https://supabase.com/changelog): current target/confirmation changes.
- [Supabase logical backup/restore](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore): managed schemas, migration history and encryption-key handling.
- [Supabase restore to a new project](https://supabase.com/docs/guides/platform/clone-project): copied/manual settings, cost and copied external-job behavior.
- [Storage copy ownership](https://supabase.com/docs/guides/storage/management/copy-move-objects): copied objects inherit the copying user's ownership.
- [PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html): restore semantics and explicit error handling.
- [EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html) and [snapshot creation](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-snapshot.html): backups are operator-managed, cached writes excluded, encryption and consistency.
- [EBS pricing](https://aws.amazon.com/ebs/pricing/): quote region/storage/restore-specific costs before approval.
