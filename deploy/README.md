# Local operation and future deployment

No cloud provider is configured and no public application has been deployed.

The backend is one process. AI transcript/replay/proposals live only in bounded RAM and expire after at most 24 hours idle. Do not enable multiple workers or replicas until an equally private shared ephemeral store and run fencing have been implemented and tested. A restart ends conversational context and marks metadata interrupted; it never replays a model call.

Local PostgreSQL:

```powershell
docker compose -f deploy/compose.local.yml up -d
```

This local-only service uses a documented development password and binds to 127.0.0.1. Supabase remains the production database. Obtain real runtime/migration credentials from the user; never replace them with this password.

Build the backend locally:

```powershell
docker build -t moodprint-backend:local backend
```

The context excludes `.env`, virtual environments and tests. The image runs as UID10001. Container deployment must use a read-only root filesystem, bounded temporary storage, resource limits, TLS termination and a secret manager. No Docker socket is passed into the application. Sandbox execution is disabled because current bot tools have no code/file execution requirement.

For Supabase, use direct or session-pooler connectivity appropriate to the runtime network. psycopg prepared statements are disabled, so transaction pooling does not retain prepared/session state; use direct/session connection for Alembic. The local migration runner rejects remote hosts. Before any remote DDL: verify project/database/role, inspect schema/history, review generated SQL, obtain explicit authorization, then run the reviewed migration through the approved operational route.

`examples/runtime-role.sql` is a review template. Use a separate migration owner; the runtime role must have DML and minimal `auth.sessions(id,user_id)` read permission, with no DDL. Tables live in private `moodprint`, outside the Supabase Data API. Backend ownership checks are the current authorization layer. Direct browser database access and Data API grants are intentionally absent; RLS policies would need a separate design/test before exposing this schema.

After reviewed schema upgrades, reapply the reviewed runtime grants for newly added tables before opening traffic. Revision0004 adds owner-private age declarations;0005 widens export-job scope metadata. Readiness now expects0005_export_scope. These migrations have only been applied to local disposable development databases; hosted DDL still requires target/schema/role review and explicit authorization.

App rollback uses a previous image against a compatible expanded schema. Alembic downgrade refuses destructive rollback. Before serving a restored database, apply deletion tombstones, consent/session revocations and invalidation gates. Raw AI context must never be restored because it must never enter backups. Physical backup/provider retention and restore drills remain release gates, with evidence recorded separately.

Liveness: `/api/v1/health/live`; readiness: `/api/v1/health/ready`. Missing database, schema revision or configuration must keep readiness unavailable. Drain streams and bounded AI runs before stopping. Privacy-safe logs contain request IDs and error classes, not request bodies, SQL parameters, provider tokens or transcripts.
