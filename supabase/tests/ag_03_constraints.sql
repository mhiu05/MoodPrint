begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();

insert into auth.users(id) values ('00000000-0000-4000-8000-0000000000a1');
insert into app.profiles(user_id,nickname) values ('00000000-0000-4000-8000-0000000000a1','User A');
insert into app.conversations(id,owner_id,title) values
 ('10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','User A'),
 ('10000000-0000-4000-8000-0000000000a2','00000000-0000-4000-8000-0000000000a1','A2');
insert into app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,tools_version) values
 ('20000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','completed','synthetic','v','v');
insert into app.cases(id,owner_id,template) values ('40000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','TPL-FREE');
insert into app.messages(id,conversation_id,owner_id,role,content) values
 ('30000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','assistant','m');
insert into app.evidence_items(id,owner_id,kind,origin,original_text) values
 ('50000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','text_note','user_entered','note');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-0000000000a1","role":"authenticated"}',true);

-- P-AG-04: check constraints.
select lives_ok($$insert into app.agent_proposals(id,owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('60000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{"d":1}',repeat('a',64),'{"s":1}','call-1',now()+interval '30 minutes')$$,'a valid proposal inserts');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{"d":2}',repeat('a',64),'{"s":1}','call-1',now()+interval '30 minutes')$$,'23505',null,'the same request key cannot create a second proposal');
select throws_ok($$insert into app.agent_proposals(id,owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-0000-0000-000000000000','00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','nil',now()+interval '30 minutes')$$,'23514',null,'the nil UUID is not a valid server id');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','delete_case','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','bad-kind',now()+interval '30 minutes')$$,'23514',null,'unknown proposal kind is refused');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{}','nothex','{}','bad-hash',now()+interval '30 minutes')$$,'23514',null,'payload hash must be sha256 hex');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','{}',repeat('a',64),'{}','past',now()-interval '1 minute')$$,'23514',null,'expiry must be after creation');
select throws_ok($$insert into app.agent_proposals(owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,request_key,expires_at)
  values ('00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','case_event','40000000-0000-4000-8000-0000000000a1','[]',repeat('a',64),'{}','arr',now()+interval '30 minutes')$$,'23514',null,'payload must be a JSON object');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key,difficulty)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','principal','x',1)$$,'23514',null,'roleplay role is limited to teacher/parent/trusted_adult');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key,difficulty)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','teacher','x',4)$$,'23514',null,'roleplay difficulty is 1..3');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key,scenario_context)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','teacher','x',repeat('x',801))$$,'23514',null,'scenario context is capped at 800 characters');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key,user_goal)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','teacher','x',repeat('x',301))$$,'23514',null,'user goal is capped at 300 characters');
select lives_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key)
  values ('80000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','teacher','teacher-group-chat')$$,'a valid roleplay session inserts');
select throws_ok($$insert into app.roleplay_sessions(id,owner_id,conversation_id,role,scenario_key)
  values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','10000000-0000-4000-8000-0000000000a1','parent','parent-first-talk')$$,'23505',null,'one roleplay session per conversation');
select throws_ok($$update app.roleplay_sessions set role='parent' where id='80000000-0000-4000-8000-0000000000a1'$$,'42501',null,'persona cannot change mid-session');
select throws_ok($$update app.roleplay_sessions set scenario_context='changed' where id='80000000-0000-4000-8000-0000000000a1'$$,'42501',null,'scenario cannot change mid-session');
select lives_ok($$update app.roleplay_sessions set turn_count=2 where id='80000000-0000-4000-8000-0000000000a1'$$,'turn count advances');
select lives_ok($$update app.roleplay_sessions set status='completed',completed_at=now(),feedback='{"summary":"ok"}' where id='80000000-0000-4000-8000-0000000000a1'$$,'complete stores feedback');
with changed as (update app.roleplay_sessions set feedback='{"summary":"rewritten"}' where id='80000000-0000-4000-8000-0000000000a1' returning 1)
  select is(count(*)::int,0,'completed session feedback is frozen') from changed;
select lives_ok($$insert into app.analysis_requests(id,owner_id,evidence_id,consent_version,consent_at,source_sha256,request_sha256)
  values ('70000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','50000000-0000-4000-8000-0000000000a1','consent-v1',now(),repeat('c',64),repeat('d',64))$$,'a running analysis request inserts');
select throws_ok($$update app.analysis_requests set consent_version='other' where id='70000000-0000-4000-8000-0000000000a1'$$,'42501',null,'consent cannot be rewritten');
select throws_ok($$update app.analysis_requests set source_sha256=repeat('e',64) where id='70000000-0000-4000-8000-0000000000a1'$$,'42501',null,'source digest cannot be rewritten');
select throws_ok($$update app.analysis_requests set status='succeeded' where id='70000000-0000-4000-8000-0000000000a1'$$,'23514',null,'a finished status needs finished_at');
select lives_ok($$update app.analysis_requests set status='failed',error_code='model_error',finished_at=now() where id='70000000-0000-4000-8000-0000000000a1'$$,'a request can fail once');
with changed as (update app.analysis_requests set status='running',finished_at=null where id='70000000-0000-4000-8000-0000000000a1' returning 1)
  select is(count(*)::int,0,'a finished request cannot be re-run in place') from changed;

-- Insert-only tables.
select lives_ok($$insert into app.message_attachments(message_id,owner_id,evidence_id) values ('30000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','50000000-0000-4000-8000-0000000000a1')$$,'attach own evidence');
select throws_ok($$insert into app.message_attachments(message_id,owner_id,evidence_id) values ('30000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','50000000-0000-4000-8000-0000000000a1')$$,'23505',null,'the same attachment cannot be added twice');
select throws_ok($$update app.message_attachments set evidence_id=gen_random_uuid()$$,'42501',null,'attachments cannot be edited');
select lives_ok($$insert into app.message_assessments(message_id,owner_id,run_id,structured) values ('30000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','{"urgency":"none"}')$$,'store structured output');
select throws_ok($$insert into app.message_assessments(message_id,owner_id,run_id,structured) values ('30000000-0000-4000-8000-0000000000a1','00000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','{"urgency":"immediate"}')$$,'23505',null,'one assessment per message');
select throws_ok($$update app.message_assessments set structured='{"urgency":"none"}'$$,'42501',null,'assessments cannot be edited');
select throws_ok($$insert into app.message_assessments(message_id,owner_id,run_id,structured) values (gen_random_uuid(),'00000000-0000-4000-8000-0000000000a1','20000000-0000-4000-8000-0000000000a1','[]')$$,'23514',null,'structured output must be an object');
reset role;

-- P-AG-05: cascades clean everything up.
delete from app.conversations where id='10000000-0000-4000-8000-0000000000a1';
select is((select count(*)::int from app.agent_proposals where owner_id='00000000-0000-4000-8000-0000000000a1'),0,'deleting a conversation removes its proposals');
select is((select count(*)::int from app.roleplay_sessions where owner_id='00000000-0000-4000-8000-0000000000a1'),0,'deleting a conversation removes its roleplay session');
select is((select count(*)::int from app.message_attachments where owner_id='00000000-0000-4000-8000-0000000000a1'),0,'deleting a conversation removes attachments');
select is((select count(*)::int from app.message_assessments where owner_id='00000000-0000-4000-8000-0000000000a1'),0,'deleting a conversation removes assessments');
delete from auth.users where id='00000000-0000-4000-8000-0000000000a1';
select is((select count(*)::int from app.analysis_requests where owner_id='00000000-0000-4000-8000-0000000000a1'),0,'deleting the user removes analysis requests');
select * from finish();
rollback;
