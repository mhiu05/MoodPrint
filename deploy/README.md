# Local operation and future deployment

AWS staging infrastructure is provisioned for `moodprint.duckdns.org`; the application will be considered deployed after a verified image release passes health checks. See [AWS staging deployment](aws/README.md).

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

Sau khi nâng schema đã được review, cấp lại quyền runtime cho các bảng mới trước khi mở traffic. Source hiện kết thúc ở `0010_account_deletion`; `/api/v1/health/ready` yêu cầu revision này và helper Supabase Auth đã review. Probe chỉ đọc ngày 25/10/2026 thấy revision 0010 trên cả hai URL remote đang cấu hình; DDL hosted vẫn cần review target/schema/role/SQL và chấp thuận riêng. Xem [migration readiness](../docs/deployment/migration-readiness.md).

App rollback uses a previous image against a compatible expanded schema. Alembic downgrade refuses destructive rollback. Before serving a restored database, apply deletion tombstones, consent/session revocations and invalidation gates. Raw AI context must never be restored because it must never enter backups. Physical backup/provider retention and restore drills remain release gates, with evidence recorded separately.

Liveness: `/api/v1/health/live`; readiness: `/api/v1/health/ready`. Missing database, schema revision or configuration must keep readiness unavailable. Drain streams and bounded AI runs before stopping. Privacy-safe logs contain request IDs and error classes, not request bodies, SQL parameters, provider tokens or transcripts.

Chuẩn bị AWS staging và xác minh local: [tài liệu triển khai](../docs/deployment/README.md); xem thêm [vận hành AWS release poller](aws/README.md). Image production dùng `backend/Dockerfile` và `frontend/Dockerfile`; `deploy/compose.staging.yml` phục vụ cả hai qua `deploy/Caddyfile` với một backend worker.
