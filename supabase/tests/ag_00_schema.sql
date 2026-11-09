begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

-- P-AG-01: every Phase 3 table exists, enforces RLS, has policies and is closed to anon.
select ok(exists(select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
                 where n.nspname='app' and c.relname=t.name and c.relkind='r'),
          format('app.%s exists',t.name))
from (values ('agent_proposals'),('analysis_requests'),('roleplay_sessions'),
             ('message_attachments'),('message_assessments')) as t(name);

select ok(c.relrowsecurity and c.relforcerowsecurity is not null, format('app.%s enforces RLS',c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='app' and c.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

select ok(exists(select 1 from pg_policy p where p.polrelid=c.oid and p.polcmd in ('r','*')),
          format('app.%s has a select policy',c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='app' and c.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

select ok(not has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
          and not has_any_column_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,REFERENCES'),
          format('anon has no privileges on app.%s',c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='app' and c.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

select ok(not has_table_privilege('service_role',c.oid,'SELECT,INSERT,UPDATE,DELETE'),
          format('service_role has no privileges on app.%s',c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='app' and c.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

-- Nothing may delete these rows directly; parents cascade instead.
select ok(not has_table_privilege('authenticated',c.oid,'DELETE'),
          format('authenticated cannot DELETE from app.%s',c.relname))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='app' and c.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

-- Insert-only tables expose no UPDATE.
select ok(not has_table_privilege('authenticated','app.message_attachments','UPDATE'),'attachments are insert-only');
select ok(not has_table_privilege('authenticated','app.message_assessments','UPDATE'),'assessments are insert-only');

-- P-AG-06: every FK of the new tables has a covering index.
select ok(exists (
  select 1 from pg_index i
  where i.indrelid=c.conrelid and i.indisvalid
    and (i.indpred is null or pg_get_expr(i.indpred,i.indrelid)=format('(%I IS NOT NULL)',
      (select attname from pg_attribute where attrelid=c.conrelid and attnum=c.conkey[1])))
    and (i.indkey::smallint[])[0:cardinality(c.conkey)-1] @> c.conkey
), format('%s has a covering index',c.conname))
from pg_constraint c
join pg_class t on t.oid=c.conrelid
join pg_namespace n on n.oid=t.relnamespace
where c.contype='f' and n.nspname='app'
  and t.relname in ('agent_proposals','analysis_requests','roleplay_sessions','message_attachments','message_assessments');

-- Content columns are closed to client updates (column-level grants).
select ok(not has_column_privilege('authenticated','app.agent_proposals',c,'UPDATE'),
          format('authenticated cannot UPDATE agent_proposals.%s',c))
from unnest(array['payload','payload_sha256','preview','kind','target_case_id','request_key','expires_at','owner_id']) as c;
select ok(has_column_privilege('authenticated','app.agent_proposals','status','UPDATE'),'status stays updatable');
select ok(not has_column_privilege('authenticated','app.analysis_requests','consent_version','UPDATE'),'consent is immutable');
select ok(not has_column_privilege('authenticated','app.roleplay_sessions','scenario_context','UPDATE'),'scenario is immutable');

select * from finish();
rollback;
