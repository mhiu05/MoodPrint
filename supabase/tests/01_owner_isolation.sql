begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

insert into auth.users(id) values
 ('00000000-0000-4000-8000-000000000001'),('00000000-0000-4000-8000-000000000002');
insert into app.profiles(user_id,nickname) values
 ('00000000-0000-4000-8000-000000000001','User A'),('00000000-0000-4000-8000-000000000002','User B');
insert into app.conversations(id,owner_id,title) values
 ('10000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','A'),
 ('10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002','B');
insert into app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,tools_version) values
 ('20000000-0000-4000-8000-000000000002','10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002','completed','synthetic','v1','v1');
insert into app.messages(id,conversation_id,owner_id,role,content) values
 ('30000000-0000-4000-8000-000000000002','10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002','user','synthetic private message');
insert into app.tool_approvals(run_id,owner_id,tool_name,tool_call_id,arguments_preview,run_state,expires_at) values
 ('20000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002','test','call1','{}','{}',now()+interval '1 hour');
insert into app.memory_candidates(owner_id,category,content,source_kind) values
 ('00000000-0000-4000-8000-000000000002','preference','synthetic candidate','agent_proposed');
insert into app.user_memories(owner_id,category,content,content_hash,source_kind) values
 ('00000000-0000-4000-8000-000000000002','preference','synthetic memory','hash-b','user_created');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
select is((select count(*)::int from app.profiles),1,'A sees only own profile');
select is((select count(*)::int from app.conversations),1,'A sees only own conversation');
select is((select count(*)::int from app.messages),0,'A cannot read B transcript');
select is((select count(*)::int from app.agent_runs),0,'A cannot read B runs');
select is((select count(*)::int from app.tool_approvals),0,'A cannot read B approval/state');
select is((select count(*)::int from app.memory_candidates),0,'A cannot read B candidates');
select is((select count(*)::int from app.user_memories),0,'A cannot read B memories');
with changed as (update app.profiles set nickname='Stolen' where user_id='00000000-0000-4000-8000-000000000002' returning 1) select is(count(*)::int,0,'A cannot change B profile') from changed;
with changed as (update app.conversations set title='Stolen' where owner_id='00000000-0000-4000-8000-000000000002' returning 1) select is(count(*)::int,0,'A cannot change B conversation') from changed;
with changed as (update app.messages set content='Stolen' returning 1) select is(count(*)::int,0,'A cannot change B message') from changed;
with changed as (update app.agent_runs set error_code='stolen' returning 1) select is(count(*)::int,0,'A cannot change B run') from changed;
with changed as (update app.tool_approvals set status='approved' returning 1) select is(count(*)::int,0,'A cannot decide B approval') from changed;
with changed as (update app.memory_candidates set status='approved' returning 1) select is(count(*)::int,0,'A cannot decide B candidate') from changed;
with changed as (update app.user_memories set content='Stolen' returning 1) select is(count(*)::int,0,'A cannot change B memory') from changed;
with gone as (delete from app.messages returning 1) select is(count(*)::int,0,'A cannot delete B transcript') from gone;
with gone as (delete from app.memory_candidates returning 1) select is(count(*)::int,0,'A cannot delete B candidates') from gone;
with gone as (delete from app.user_memories returning 1) select is(count(*)::int,0,'A cannot delete B memories') from gone;
select throws_ok($$insert into app.conversations(owner_id) values ('00000000-0000-4000-8000-000000000002')$$,'42501',null,'A cannot create rows for B');
select throws_ok($$update app.conversations set owner_id='00000000-0000-4000-8000-000000000002' where title='A'$$,'42501',null,'A cannot reassign ownership');
reset role;
select is((select content from app.messages limit 1),'synthetic private message','cross-owner mutation did not affect stored content');
select * from finish();
rollback;
