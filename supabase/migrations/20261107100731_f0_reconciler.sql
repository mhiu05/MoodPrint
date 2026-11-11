create function app_private.reconcile_stale_runs(stale_after interval)
returns integer language plpgsql security definer set search_path='' as $$
declare affected integer;
begin
  if stale_after < interval '30 seconds' then
    raise exception 'stale threshold must be at least 30 seconds' using errcode='22023';
  end if;
  with stale as (
    select id from app.agent_runs
    where status='running' and heartbeat_at < now()-stale_after
    order by heartbeat_at limit 100 for update skip locked
  ), changed as (
    update app.agent_runs r set status='interrupted',error_code='heartbeat_lost',finished_at=now()
    from stale where r.id=stale.id returning r.id
  ) select count(*)::integer into affected from changed;
  -- Awaiting approval is intentionally not timed out by a heartbeat clock.
  with expired as (
    select id,run_id from app.tool_approvals
    where status='pending' and expires_at < now()
    order by expires_at limit 100 for update skip locked
  ), decided as (
    update app.tool_approvals a set status='expired',decided_at=now()
    from expired e where a.id=e.id returning a.run_id
  ) update app.agent_runs r set status='interrupted',error_code='approval_expired',finished_at=now()
    where r.id in(select run_id from decided) and r.status='awaiting_approval';
  return affected;
end $$;
revoke all on function app_private.reconcile_stale_runs(interval) from public,anon,authenticated,service_role;
grant execute on function app_private.reconcile_stale_runs(interval) to safevoice_api;

-- Evidence is a Phase 1 table. Its purge functions belong in f1_evidence,
-- alongside the table and immutable-column trigger, rather than placeholder RPCs.
