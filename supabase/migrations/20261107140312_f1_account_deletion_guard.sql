alter table app.profiles add column deletion_started_at timestamptz;
create function app_private.guard_account_deletion() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if old.deletion_started_at is not null and new.deletion_started_at is distinct from old.deletion_started_at then
    raise exception 'Account deletion cannot be reverted' using errcode='23514';
  end if;
  return new;
end $$;
revoke all on function app_private.guard_account_deletion() from public,anon,service_role;
grant execute on function app_private.guard_account_deletion() to authenticated;
create trigger profile_deletion_guard before update on app.profiles for each row execute function app_private.guard_account_deletion();
