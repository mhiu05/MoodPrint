begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

-- Defense in depth: private ingestion is an access class, never an RLS waiver.
-- Exact opt-in marker: COMMENT ON TABLE knowledge.<table> IS
-- 'moodprint:private_ingestion'. Grant/policy changes belong in reviewed migrations.
select ok(c.relrowsecurity and exists(select 1 from pg_policy p where p.polrelid=c.oid),
          format('%I.%I satisfies schema policy manifest',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname in ('app','agent_store','knowledge') and c.relkind in ('r','p');

select ok(not exists(
    select 1 from pg_policy p cross join lateral unnest(p.polroles) as pr(role_oid)
    left join pg_roles r on r.oid=pr.role_oid
    where p.polrelid=c.oid and
          (pr.role_oid=0 or r.rolname in ('anon','authenticated','service_role'))
), format('private ingestion %I.%I has no public/client policy',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p')
  and obj_description(c.oid,'pg_class')='moodprint:private_ingestion';

select ok(exists(
    select 1 from pg_policy p cross join lateral unnest(p.polroles) as pr(role_oid)
    join pg_roles r on r.oid=pr.role_oid
    where p.polrelid=c.oid and p.polcmd in ('*','a','w','d')
      and r.rolname not in ('anon','authenticated','service_role','postgres')
      and not r.rolsuper and not r.rolbypassrls
      and has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE')
), format('private ingestion %I.%I has an explicit restricted writer policy and grant',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p')
  and obj_description(c.oid,'pg_class')='moodprint:private_ingestion';

select * from finish();
rollback;
