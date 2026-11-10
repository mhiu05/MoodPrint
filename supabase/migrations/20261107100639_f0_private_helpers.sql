create function app_private.f_unaccent(text) returns text
language sql immutable strict parallel safe security invoker
set search_path = ''
as $$ select extensions.unaccent('extensions.unaccent'::regdictionary, $1) $$;

create function app_private.touch_updated_at() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin new.updated_at := now(); return new; end $$;

create function app_private.bump_version() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin new.version := old.version + 1; return new; end $$;

revoke all on function app_private.f_unaccent(text), app_private.touch_updated_at(), app_private.bump_version() from public, anon, service_role;
grant execute on function app_private.f_unaccent(text), app_private.touch_updated_at(), app_private.bump_version() to authenticated;
