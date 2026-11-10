begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

insert into auth.users(id) values ('00000000-0000-4000-8000-0000000000a1');
insert into app.profiles(user_id,nickname) values ('00000000-0000-4000-8000-0000000000a1','User A');
insert into app.conversations(id,owner_id,title) values ('10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','User A');
insert into app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,tools_version) values
 ('20000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','awaiting_approval','synthetic','v','v');
insert into app.cases(id,owner_id,template) values ('40000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','TPL-FREE');
insert into app.agent_proposals(id,owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,base_version,request_key,expires_at) values
 ('60000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{"description":"x"}',repeat('a',64),'{"summary":"x"}',1,'call-1',now()+interval '30 minutes'),
 ('60000000-0000-4000-8000-0000000000a2','00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','action_plan','40000000-0000-4000-8000-0000000000a1','{"goal":"z"}',repeat('c',64),'{"summary":"z"}',null,'call-2',now()+interval '30 minutes');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-0000000000a1","role":"authenticated"}',true);

-- P-AG-03: stored content cannot be rewritten by any client role, not even the owner.
select throws_ok(format($q$update app.agent_proposals set %s where id='60000000-0000-4000-8000-0000000000a1'$q$, assignment),
                 '42501',null,format('%s is not updatable',col))
from (values
  ('payload',$q$payload='{"description":"changed"}'$q$),
  ('payload_sha256',$q$payload_sha256=repeat('f',64)$q$),
  ('preview',$q$preview='{"summary":"other"}'$q$),
  ('kind',$q$kind='action_plan'$q$),
  ('target_case_id',$q$target_case_id=gen_random_uuid()$q$),
  ('request_key',$q$request_key='other'$q$),
  ('expires_at',$q$expires_at=now()+interval '9 days'$q$),
  ('run_id',$q$run_id=gen_random_uuid()$q$),
  ('conversation_id',$q$conversation_id=gen_random_uuid()$q$),
  ('owner_id',$q$owner_id=gen_random_uuid()$q$),
  ('base_version',$q$base_version=2$q$),
  ('created_at',$q$created_at=now()$q$),
  ('id',$q$id=gen_random_uuid()$q$)
) as t(col,assignment);

-- Rows are born "proposed": a client cannot insert an already-decided proposal.
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at,status,approval_binding,decided_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','pre-approved',now()+interval '1 hour','approved','{"decision":"approve","payload_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',now())$$,
  '42501',null,'cannot insert an approved proposal');

-- Approval requires a binding that names this exact payload hash and an approve decision.
select throws_ok($$update app.agent_proposals set status='approved', decided_at=now() where id='60000000-0000-4000-8000-0000000000a1'$$,'23514',null,'approved needs an approval binding');
select throws_ok($$update app.agent_proposals set status='approved', decided_at=now(),
  approval_binding='{"decision":"approve","payload_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'
  where id='60000000-0000-4000-8000-0000000000a1'$$,'23514',null,'binding for a different payload hash is refused');
select throws_ok($$update app.agent_proposals set status='approved', decided_at=now(),
  approval_binding='{"decision":"reject","payload_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
  where id='60000000-0000-4000-8000-0000000000a1'$$,'23514',null,'a rejection cannot be stored as an approval');
select throws_ok($$update app.agent_proposals set status='proposed' where id='60000000-0000-4000-8000-0000000000a1'$$,'42501',null,'a proposal cannot be re-opened to proposed');
select lives_ok($$update app.agent_proposals set status='approved', decided_at=now(),
  approval_binding='{"decision":"approve","approval_id":"90000000-0000-4000-8000-0000000000a1","tool_call_id":"call-1","payload_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
  where id='60000000-0000-4000-8000-0000000000a1'$$,'a correctly bound approval succeeds');

-- Applying needs the result and timestamp to be recorded together.
select throws_ok($$update app.agent_proposals set status='applied' where id='60000000-0000-4000-8000-0000000000a1'$$,'23514',null,'applied needs applied_at and result');
select lives_ok($$update app.agent_proposals set status='applied', applied_at=now(), result='{"eventId":"e1"}' where id='60000000-0000-4000-8000-0000000000a1'$$,'approved proposal can be applied');

-- Terminal rows are frozen: the update matches no row at all.
with changed as (update app.agent_proposals set result='{"eventId":"e2"}' where id='60000000-0000-4000-8000-0000000000a1' returning 1)
  select is(count(*)::int,0,'applied proposal result cannot change') from changed;
with changed as (update app.agent_proposals set status='failed' where id='60000000-0000-4000-8000-0000000000a1' returning 1)
  select is(count(*)::int,0,'applied proposal cannot change state') from changed;

-- Reject is final.
select lives_ok($$update app.agent_proposals set status='rejected', decided_at=now() where id='60000000-0000-4000-8000-0000000000a2'$$,'user can reject');
with changed as (update app.agent_proposals set status='approved', decided_at=now() where id='60000000-0000-4000-8000-0000000000a2' returning 1)
  select is(count(*)::int,0,'rejected proposal cannot be approved later') from changed;
reset role;
select is((select status from app.agent_proposals where id='60000000-0000-4000-8000-0000000000a2'),'rejected','rejected proposal stays rejected');
select is((select payload->>'description' from app.agent_proposals where id='60000000-0000-4000-8000-0000000000a1'),'x','payload unchanged after every attempt');
select * from finish();
rollback;
