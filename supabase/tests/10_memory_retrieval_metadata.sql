begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();
insert into auth.users(id) values('00000000-0000-4000-8000-000000000001');
insert into app.user_memories(id,owner_id,category,content,content_hash,source_kind,updated_at)
values('a0000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','goal','Synthetic older approved memory','metadata-a','user_created',now()-interval '100 days');
update app.user_memories set last_retrieved_at=now()
where id='a0000000-0000-4000-8000-000000000001';
select is((select updated_at from app.user_memories where id='a0000000-0000-4000-8000-000000000001'),now()-interval '100 days','retrieving memory does not refresh confirmation age');
select is((select version from app.user_memories where id='a0000000-0000-4000-8000-000000000001'),1,'retrieving memory does not create a new content version');
select is((select last_retrieved_at from app.user_memories where id='a0000000-0000-4000-8000-000000000001'),now(),'retrieval metadata is still recorded');
update app.user_memories set content='Synthetic changed approved memory',content_hash='metadata-b'
where id='a0000000-0000-4000-8000-000000000001';
select is((select updated_at from app.user_memories where id='a0000000-0000-4000-8000-000000000001'),now(),'changing content updates timestamp');
select is((select version from app.user_memories where id='a0000000-0000-4000-8000-000000000001'),2,'changing content bumps version');
select * from finish();
rollback;
