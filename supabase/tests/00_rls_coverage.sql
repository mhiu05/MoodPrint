begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

select ok(exists(select 1 from pg_namespace where nspname='app'), 'domain schema exists');
select is((select count(*)::int from pg_tables where schemaname='app'), 8, 'all eight Phase 0 domain tables exist');
select is((select count(*)::int from pg_tables where schemaname='agent_store'), 2, 'SDK tables exist');
select ok(c.relrowsecurity, format('%I.%I enforces RLS', n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname in ('app','agent_store') and c.relkind='r';
select ok(exists(select 1 from pg_policy p where p.polrelid=c.oid),
          format('%I.%I has a policy',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname in ('app','agent_store') and c.relkind='r';
select is((select count(*)::int from pg_tables where schemaname='public'), 0, 'public contains no business tables');
select * from finish();
rollback;
