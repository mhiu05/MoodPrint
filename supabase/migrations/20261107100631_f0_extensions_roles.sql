create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists unaccent with schema extensions;

create schema app;
create schema app_private;
create schema agent_store;
revoke all on schema app, app_private, agent_store from public, anon, authenticated, service_role;
grant usage on schema app to authenticated;
grant usage on schema app_private to authenticated;

create role safevoice_api nologin noinherit nobypassrls nosuperuser nocreatedb nocreaterole;
grant authenticated to safevoice_api with inherit false, set true;
grant usage on schema agent_store, app_private to safevoice_api;
-- No table/function defaults inherited from Supabase's exposed public schema.
alter default privileges in schema app, app_private, agent_store revoke all on tables from public, anon, authenticated, service_role;
alter default privileges in schema app, app_private, agent_store revoke all on functions from public, anon, authenticated, service_role;
alter default privileges in schema app, app_private, agent_store revoke all on sequences from public, anon, authenticated, service_role;

do $$ begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end $$;
