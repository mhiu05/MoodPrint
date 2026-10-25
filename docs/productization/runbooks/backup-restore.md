# Backup and restore runbook

Audience: the MoodPrint operator (database access on a workstation with Docker and libpq tools).
Scope: the private `moodprint` schema on the hosted Supabase project. Supabase plan backups / PITR
entitlements are **unverified (Q-04)**; this logical backup is the recovery path we control.

> Every step that reads from or writes to the hosted database needs the operator's explicit approval
> at the time. Never restore into the hosted project; restores go into a new disposable `*_test`
> database (drills) or a new database prepared with separate approval (real recovery).

## 1. Schedule

| When | What |
|---|---|
| Weekly (Monday, Asia/Bangkok) | Logical dump of `moodprint`, encrypted, stored off-host |
| Before every hosted migration | Fresh dump (existing practice: `C:\Users\<operator>\moodprint-backups\`) |
| Quarterly | Restore drill into `restore_test`, evidence in `docs/productization/evidence/restore-drill.md` |

Keep the last 8 weekly dumps and every pre-migration dump for one release after the migration.

## 2. Take a backup

Run libpq tools inside the local `postgres:17` container so versions match. Connection values come
from the operator's secret store, never from `backend/.env` and never typed into shell history.

```sh
# PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD exported from the secret store for this shell only.
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker run --rm -e PGHOST -e PGPORT -e PGUSER -e PGDATABASE -e PGPASSWORD -e PGSSLMODE=require \
  -v "$PWD:/out" postgres:17 \
  pg_dump --schema=moodprint --format=custom --no-owner --no-privileges \
  --file="/out/moodprint-$stamp.dump"
sha256sum "moodprint-$stamp.dump" > "moodprint-$stamp.dump.sha256"
```

Encrypt before it leaves the workstation (age or gpg with the operator's recovery key), then delete
the plaintext dump:

```sh
age -r "<operator recovery public key>" -o "moodprint-$stamp.dump.age" "moodprint-$stamp.dump"
shred -u "moodprint-$stamp.dump"   # or Remove-Item on Windows after verifying the .age file
```

Store the `.age` file and its `.sha256` in the off-host location (owner decision, Q-04). Record the
stamp, size and hash in the operator log.

## 3. Restore drill (quarterly, local only)

1. Decrypt the chosen dump to the workstation.
2. Create a fresh local database: the name must end `_test` (for example `restore_test`).
3. Restore and compare:

```sh
pg_restore --no-owner --no-privileges --exit-on-error -d restore_test moodprint-<stamp>.dump
psql -d restore_test -Atc "select version_num from moodprint.alembic_version"
# Compare exact row counts per table against the counts recorded at dump time (§2 log or the
# source if it is local). Every table in moodprint must match.
```

4. Record source, revision, per-table counts (source vs restored), duration and the outcome in
   `docs/productization/evidence/restore-drill.md`. Drop `restore_test` afterwards.

A drill passes when the revision matches, every table count matches and `pg_restore` exits 0.

## 4. Real recovery (data corruption or loss)

Approval required at each step. Outline:

1. Freeze writes: stop the backend container (readiness goes down; Caddy serves the error page).
2. Take a dump of the damaged state (for forensics) before touching anything.
3. Restore the last good dump into a **new** database or schema; never overwrite in place.
4. Before serving the restored data, re-apply what happened after the dump was taken (deploy/README.md):
   deletion tombstones (accounts deleted since the dump must be deleted again), consent withdrawals,
   session revocations, moderation suspensions/restrictions and invalidation gates.
5. Re-grant the runtime role on every table (`scripts/provision_supabase_runtime.py` review path),
   run `scripts/inspect_database.py` and Supabase advisors (read-only), then point the backend at it.
6. Loss window = time since the dump. Tell affected users honestly if data was lost.

Raw AI context must never be restored: it is not supposed to be in backups. If a dump contains it,
stop and treat it as a privacy incident (incident runbook).
