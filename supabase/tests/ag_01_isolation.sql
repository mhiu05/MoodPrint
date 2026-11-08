begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

-- Two synthetic users with a full object graph each.
insert into auth.users(id) values
 ('00000000-0000-4000-8000-0000000000a1'),('00000000-0000-4000-8000-0000000000b2');
insert into app.profiles(user_id,nickname) values
 ('00000000-0000-4000-8000-0000000000a1','User A'),('00000000-0000-4000-8000-0000000000b2','User B');
insert into app.conversations(id,owner_id,title) values
 ('10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','User A'),
 ('10000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','User B');
insert into app.conversations(id,owner_id,title) values
 ('10000000-0000-4000-8000-0000000000b3','00000000-0000-4000-8000-0000000000b2','B second');
insert into app.messages(id,conversation_id,owner_id,role,content) values
 ('30000000-0000-4000-8000-0000000000b3','10000000-0000-4000-8000-0000000000b3','00000000-0000-4000-8000-0000000000b2','assistant','synthetic b3');
insert into app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,tools_version) values
 ('20000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','completed','synthetic','v','v'),
 ('20000000-0000-4000-8000-0000000000b2','10000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','completed','synthetic','v','v');
insert into app.cases(id,owner_id,template) values
 ('40000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','TPL-FREE'),
 ('40000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','TPL-FREE');
insert into app.messages(id,conversation_id,owner_id,role,content) values
 ('30000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','assistant','synthetic a'),
 ('30000000-0000-4000-8000-0000000000b2','10000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','assistant','synthetic b');
insert into app.evidence_items(id,owner_id,kind,origin,original_text) values
 ('50000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','text_note','user_entered','note a'),
 ('50000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','text_note','user_entered','note b');

insert into app.agent_proposals(id,owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at) values
 ('60000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','10000000-0000-4000-8000-0000000000b2','20000000-0000-4000-8000-0000000000b2','case_event','40000000-0000-4000-8000-0000000000b2','{"k":"b"}',repeat('b',64),'{"s":"b"}','call-b',now()+interval '30 minutes');
insert into app.analysis_requests(id,owner_id,evidence_id,consent_version,consent_at,source_sha256,request_sha256) values
 ('70000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','50000000-0000-4000-8000-0000000000b2','c1',now(),repeat('c',64),repeat('d',64));
insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key) values
 ('80000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','10000000-0000-4000-8000-0000000000b2','teacher','teacher-group-chat');
insert into app.message_attachments(message_id,owner_id,evidence_id) values
 ('30000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','50000000-0000-4000-8000-0000000000b2');
insert into app.message_assessments(message_id,owner_id,run_id,structured) values
 ('30000000-0000-4000-8000-0000000000b2','00000000-0000-4000-8000-0000000000b2','20000000-0000-4000-8000-0000000000b2','{"urgency":"none"}');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-0000000000a1","role":"authenticated"}',true);

-- P-AG-02: user A sees and changes nothing of user B's.
select is((select count(*)::int from app.agent_proposals),0,'A cannot read B proposals');
select is((select count(*)::int from app.analysis_requests),0,'A cannot read B analysis requests');
select is((select count(*)::int from app.roleplay_sessions),0,'A cannot read B roleplay sessions');
select is((select count(*)::int from app.message_attachments),0,'A cannot read B attachments');
select is((select count(*)::int from app.message_assessments),0,'A cannot read B assessments');
with changed as (update app.agent_proposals set status='rejected' returning 1) select is(count(*)::int,0,'A cannot decide B proposal') from changed;
with changed as (update app.roleplay_sessions set status='abandoned',completed_at=now() returning 1) select is(count(*)::int,0,'A cannot end B roleplay') from changed;
with changed as (update app.analysis_requests set status='failed',finished_at=now() returning 1) select is(count(*)::int,0,'A cannot finish B analysis') from changed;

-- A cannot attach a proposal to B's conversation, run, or case (composite foreign keys).
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000b2','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','x1',now()+interval '1 hour')$$,
  '23503',null,'A cannot bind a proposal to B conversation');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000b2','case_event','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','x2',now()+interval '1 hour')$$,
  '23503',null,'A cannot bind a proposal to B run');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000b2','{}',repeat('a',64),'{}','x3',now()+interval '1 hour')$$,
  '23503',null,'A cannot target B case');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000b2','10000000-0000-4000-8000-0000000000b2','20000000-0000-4000-8000-0000000000b2','case_event','40000000-0000-4000-8000-0000000000b2','{}',repeat('a',64),'{}','x4',now()+interval '1 hour')$$,
  '42501',null,'A cannot create a proposal owned by B');
select throws_ok($$insert into app.analysis_requests(id,owner_id,evidence_id,consent_version,consent_at,source_sha256,request_sha256)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','50000000-0000-4000-8000-0000000000b2','c',now(),repeat('c',64),repeat('d',64))$$,
  '23503',null,'A cannot analyse B evidence');
select throws_ok($$insert into app.message_attachments(message_id,owner_id,evidence_id)
  values ('30000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','50000000-0000-4000-8000-0000000000b2')$$,
  '23503',null,'A cannot attach B evidence to A message');
select throws_ok($$insert into app.message_assessments(message_id,owner_id,run_id,structured)
  values ('30000000-0000-4000-8000-0000000000b3','00000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','{}')$$,
  '23503',null,'A cannot write an assessment for B message');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000b3','parent','parent-first-talk')$$,
  '23503',null,'A cannot start roleplay in B conversation');
reset role;
select is((select status from app.agent_proposals where id='60000000-0000-4000-8000-0000000000b2'),'proposed','B proposal untouched by A');
select * from finish();
rollback;
