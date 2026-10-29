# Local operation and future deployment

AWS staging infrastructure is provisioned for `moodprint.duckdns.org`; the application will be considered deployed after a verified image release passes health checks. See [AWS staging deployment](aws/README.md).

The supported backend topology is one worker/replica. Temporary conversation context, active runs and stream state live in bounded RAM; temporary conversations expire after 24 hours idle. Opted-in saved transcripts and memory proposals have separate PostgreSQL persistence and lifecycle rules. Do not enable multiple workers or replicas until shared ephemeral state and run fencing have been implemented and tested. A restart interrupts active runs and never replays a model call. See [context and memory](../docs/agents/context-memory.md).

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

`examples/runtime-role.sql` is a review template. Use a separate migration owner; the runtime role needs reviewed application DML and EXECUTE on the private provider-session helper, with no DDL or direct Auth schema/table grants. The approved SECURITY DEFINER helper owner reads only the required provider session fields; the runtime-role verifier checks that raw Auth access is denied. Tables live in private `moodprint`, outside the Supabase Data API. Backend ownership checks are the current authorization layer. Direct browser database access and Data API grants are intentionally absent; RLS policies would need a separate design/test before exposing this schema.

Sau khi nâng schema đã được review, cấp quyền runtime cho các bảng mới trước khi mở traffic. `/api/v1/health/ready` kiểm tra `READY_REVISIONS` (`backend/app/core/revisions.py`) và helper Supabase Auth đã review. Head được chấp nhận hiện tại chỉ là `0018_app_feedback`; không suy ra mọi head trước đều tương thích. Hosted apply script hiện có upgrade plans đến 0014, nên 0015–0018 cần artifact/plan/review riêng trước khi áp dụng từ xa. Xem [migration runbook](../docs/supabase/migrations.md). Tài liệu không xác nhận revision hosted hiện tại.

Guest release is held by [G0–G6 and D01–D04](../docs/guest-experience/implementation/evidence/release-readiness.md). Follow the [guest-aware rollback](../docs/guest-experience/implementation/evidence/rollback.md); the original registered-only image cannot safely serve a database containing guests. All rollout flags remain off.

App rollback uses a previous image against a compatible expanded schema. Alembic downgrade refuses destructive rollback. Before serving a restored database, apply deletion tombstones, consent/session revocations and invalidation gates. Temporary raw AI context must never enter backups or be restored. Opted-in persistent transcripts are database content, so backup retention and restore privacy require separate controls. Physical backup/provider retention and restore drills remain release gates, with evidence recorded separately.

Liveness: `/api/v1/health/live`; readiness: `/api/v1/health/ready`. Missing database, schema revision or configuration must keep readiness unavailable. Drain streams and bounded AI runs before stopping. Privacy-safe logs contain request IDs and error classes, not request bodies, SQL parameters, provider tokens or transcripts.

Chuẩn bị và xác minh local: [development](../docs/development.md), [vận hành backend](../docs/backend/operations.md); xem thêm [vận hành AWS release poller](aws/README.md). Image production dùng `backend/Dockerfile` và `frontend/Dockerfile`; `deploy/compose.staging.yml` phục vụ cả hai qua `deploy/Caddyfile` với một backend worker.
