begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();
insert into auth.users(id) values
 ('00000000-0000-4000-8000-000000000001'),
 ('00000000-0000-4000-8000-000000000002');
insert into app.user_memories(id,owner_id,category,content,content_hash,source_kind) values
 ('90000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','goal','Synthetic approved memory','provenance-a','user_created'),
 ('90000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002','goal','Synthetic other owner','provenance-b','user_created');
select throws_ok($$insert into app.memory_candidates(owner_id,category,content,source_kind,status,approved_memory_id)
 values('00000000-0000-4000-8000-000000000001','goal','Synthetic cross-owner candidate','agent_proposed','approved','90000000-0000-4000-8000-000000000002')$$,
 '23503',null,'approved target cannot cross owners even for a role bypassing RLS');
insert into app.memory_candidates(owner_id,category,content,source_kind,status,approved_memory_id) values
 ('00000000-0000-4000-8000-000000000001','goal','Synthetic canonical source','agent_proposed','approved','90000000-0000-4000-8000-000000000001'),
 ('00000000-0000-4000-8000-000000000001','goal','Synthetic edited source deduped to same memory','agent_proposed','approved','90000000-0000-4000-8000-000000000001');
select is((select count(*)::integer from app.memory_candidates where approved_memory_id='90000000-0000-4000-8000-000000000001'),2,'multiple candidate approvals retain their exact final target');
delete from app.user_memories where id='90000000-0000-4000-8000-000000000001';
select is((select count(*)::integer from app.memory_candidates where owner_id='00000000-0000-4000-8000-000000000001'),0,'hard deleting memory removes all linked candidate contents');
select * from finish();
rollback;
