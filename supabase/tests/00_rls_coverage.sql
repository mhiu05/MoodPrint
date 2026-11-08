begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

select ok(exists(select 1 from pg_namespace where nspname='app'), 'domain schema exists');
select ok(exists(select 1 from pg_namespace where nspname='agent_store'), 'SDK schema exists');
-- Named baseline, mirrored from docs/implementation/schema-manifest.json.
-- Additional phase tables are allowed and inspected below, never counted.
select ok(exists(
    select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname=b.schema_name and c.relname=b.table_name and c.relkind in ('r','p')
), format('baseline table %I.%I exists',b.schema_name,b.table_name))
from (values
    ('app','action_plans'), ('app','agent_runs'), ('app','audit_events'),
    ('app','case_event_evidence'), ('app','case_events'), ('app','case_share_evidence'),
    ('app','case_shares'), ('app','cases'), ('app','conversations'),
    ('app','evidence_derivatives'), ('app','evidence_items'), ('app','knowledge_article_states'),
    ('app','memory_candidates'), ('app','messages'), ('app','plan_items'),
    ('app','profiles'), ('app','school_memberships'), ('app','schools'),
    ('app','support_drafts'), ('app','tool_approvals'), ('app','trusted_contacts'),
    ('app','user_memories'), ('agent_store','agent_messages'), ('agent_store','agent_sessions')
) as b(schema_name,table_name);
select ok(c.relrowsecurity, format('%I.%I enforces RLS', n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname in ('app','agent_store','knowledge') and c.relkind in ('r','p');
select ok(exists(select 1 from pg_policy p where p.polrelid=c.oid),
          format('%I.%I has a policy',n.nspname,c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname in ('app','agent_store','knowledge') and c.relkind in ('r','p');
select is((select count(*)::int from pg_class c join pg_namespace n on n.oid=c.relnamespace
           where n.nspname='public' and c.relkind in ('r','p')), 0, 'public contains no business tables');
select * from finish();
rollback;
