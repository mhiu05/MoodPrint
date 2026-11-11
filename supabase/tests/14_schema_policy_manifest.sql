begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

-- Defense in depth: private ingestion is an access class, never an RLS waiver.
-- Exact opt-in marker: COMMENT ON TABLE knowledge.<table> IS
-- 'safevoice:private_ingestion'. Grant/policy changes belong in reviewed migrations.
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
  and obj_description(c.oid,'pg_class')='safevoice:private_ingestion';

-- Private metadata is maintained by the existing owner/admin ingestion connection.
-- An unused writer role would only enlarge the runtime attack surface. Require the
-- owner to remain distinct from application roles and reject table OR column grants.
select ok(
    c.relowner not in ('anon'::regrole, 'authenticated'::regrole, 'service_role'::regrole, 'safevoice_api'::regrole)
    and has_table_privilege(c.relowner,c.oid,'INSERT,UPDATE,DELETE')
    and not exists(
        select 1 from pg_roles r
        where r.rolname in ('anon','authenticated','service_role','safevoice_api')
          and (has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
               or has_any_column_privilege(r.oid,c.oid,'INSERT,UPDATE,REFERENCES'))
    ), format('private ingestion %I.%I retains owner/admin writes with no runtime mutation grants',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p')
  and obj_description(c.oid,'pg_class')='safevoice:private_ingestion';

select * from finish();
rollback;
