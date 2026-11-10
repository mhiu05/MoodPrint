-- Deleting evidence cannot reset the hourly upload-init budget. The caller can
-- count only their own content-free audit events, never read the audit table.
create function app_private.own_upload_init_count() returns bigint
language sql stable security definer set search_path='' as $$
  select count(*) from app.audit_events a
  where (select auth.uid()) is not null and a.actor_id=(select auth.uid())
    and a.action='evidence.upload_initialized' and a.created_at>=now()-interval '1 hour';
$$;
revoke all on function app_private.own_upload_init_count() from public,anon,service_role;
grant execute on function app_private.own_upload_init_count() to authenticated;
