begin;
create extension if not exists pgtap with schema extensions;
set local search_path=public,extensions;
select no_plan();
insert into auth.users(id) values ('00000000-0000-4000-8000-000000000001');
insert into app.conversations(id,owner_id) values
 ('10000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001'),
 ('10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000001'),
 ('10000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000001');
insert into app.agent_runs(id,conversation_id,owner_id,model,prompt_version,tools_version,status,heartbeat_at) values
 ('20000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001','synthetic','v1','v1','running',now()-interval '10 minutes'),
 ('20000000-0000-4000-8000-000000000002','10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000001','synthetic','v1','v1','running',now()),
 ('20000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000001','synthetic','v1','v1','awaiting_approval',now()-interval '10 minutes');
select is(app_private.reconcile_stale_runs(interval '3 minutes'),1,'only stale running state is interrupted');
select is((select status from app.agent_runs where id='20000000-0000-4000-8000-000000000001'),'interrupted','stale run transitions');
select is((select status from app.agent_runs where id='20000000-0000-4000-8000-000000000002'),'running','fresh run untouched');
select is((select status from app.agent_runs where id='20000000-0000-4000-8000-000000000003'),'awaiting_approval','approval wait not subject to heartbeat expiry');
select throws_ok($$select app_private.reconcile_stale_runs(interval '1 second')$$,'22023',null,'unreasonably aggressive threshold rejected');
select * from finish();
rollback;
