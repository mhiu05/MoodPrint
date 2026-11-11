begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();
select ok(not has_schema_privilege('anon',oid,'USAGE'), 'anon cannot enter '||nspname)
from pg_namespace where nspname in ('app','app_private','agent_store','knowledge');
-- Every knowledge table is either published (SELECT only) or explicitly marked
-- private ingestion. Both classes must still have RLS and policies (00/14).
select ok(not has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
          and not has_any_column_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,REFERENCES'),
          format('anon has no privileges on %I.%I',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p');
select ok(not has_table_privilege('authenticated',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
          and not has_any_column_privilege('authenticated',c.oid,'INSERT,UPDATE,REFERENCES'),
          format('authenticated cannot write %I.%I',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p');
select ok(case when obj_description(c.oid,'pg_class')='safevoice:private_ingestion'
               then not has_table_privilege('authenticated',c.oid,'SELECT')
                    and not has_any_column_privilege('authenticated',c.oid,'SELECT')
               else has_table_privilege('authenticated',c.oid,'SELECT')
                    and has_schema_privilege('authenticated',n.oid,'USAGE') end,
          format('%I.%I has explicit published or private read grants',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='knowledge' and c.relkind in ('r','p');
select ok(not has_table_privilege('safevoice_api','app.messages','SELECT'),'login role cannot directly read transcript');
select ok(not has_table_privilege('service_role','app.messages','SELECT'),'secret HTTP role cannot directly read transcript');
select ok(not has_table_privilege('authenticated','agent_store.agent_messages','SELECT'),'user role cannot read SDK replay');
select ok(not has_function_privilege('authenticated','app_private.reconcile_stale_runs(interval)','EXECUTE'),'user cannot reconcile across owners');
select ok(has_function_privilege('safevoice_api','app_private.reconcile_stale_runs(interval)','EXECUTE'),'only backend login can reconcile');
select ok(not rolbypassrls and not rolsuper and not rolinherit and not rolcreatedb and not rolcreaterole,'login role has no elevated attributes') from pg_roles where rolname='safevoice_api';
select ok(not inherit_option and set_option,'role membership permits explicit switching only') from pg_auth_members where member='safevoice_api'::regrole and roleid='authenticated'::regrole;
-- postgres is not SUPERUSER on Supabase. Temporary membership is test-local.
grant safevoice_api to postgres;
grant usage on schema extensions to safevoice_api;
set local role safevoice_api;
select throws_ok($$select content from app.messages$$,'42501',null,'direct content read fails for background login');
select lives_ok($$select app_private.reconcile_stale_runs(interval '2 minutes')$$,'narrow reconciler executes');
reset role;
select * from finish();
rollback;
