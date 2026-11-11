begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

-- Owner/admin ingestion can still maintain private notes. All rows roll back.
insert into knowledge.sources (
  source_id, kind, publisher, title, language, country_scope,
  authority_tier, licence_class, verified_on
) values (
  'mp-privileges', 'authored', 'SafeVoice', 'Privilege test', 'vi', array['VN'],
  4, 'authored', '2026-11-09'
);
select lives_ok(
  $$insert into knowledge.source_confidential values ('mp-privileges', 'admin note')$$,
  'admin ingestion can insert private notes'
);
select lives_ok(
  $$update knowledge.source_confidential set licence_note = 'admin revised' where source_id = 'mp-privileges'$$,
  'admin ingestion can update private notes'
);
select is(
  (select licence_note from knowledge.source_confidential where source_id = 'mp-privileges'),
  'admin revised', 'admin ingestion can read its stored note'
);

select ok(
  not has_table_privilege(r.oid, 'knowledge.source_confidential', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
  and not has_any_column_privilege(r.oid, 'knowledge.source_confidential', 'SELECT,INSERT,UPDATE,REFERENCES'),
  r.rolname || ' has no private-note table or column privileges'
) from pg_roles r where r.rolname in ('anon', 'authenticated', 'safevoice_api', 'service_role');

-- postgres is not SUPERUSER on hosted Supabase; membership stays transaction-local.
grant safevoice_api to postgres;
grant usage on schema extensions to safevoice_api;
set local role safevoice_api;
select throws_ok($$insert into knowledge.source_confidential values ('mp-privileges', 'runtime note')$$,
  '42501', null, 'runtime login cannot insert private notes');
select throws_ok($$update knowledge.source_confidential set licence_note = 'runtime revised' where source_id = 'mp-privileges'$$,
  '42501', null, 'runtime login cannot update private notes');
select throws_ok($$delete from knowledge.source_confidential where source_id = 'mp-privileges'$$,
  '42501', null, 'runtime login cannot delete private notes');
select throws_ok($$select licence_note from knowledge.source_confidential$$,
  '42501', null, 'runtime login cannot read private notes');

-- The backend still switches explicitly for the public corpus read path.
set local role authenticated;
select lives_ok($$select source_id, title from knowledge.sources$$,
  'runtime authenticated read path still reads public source metadata');
select throws_ok($$select licence_note from knowledge.source_confidential$$,
  '42501', null, 'authenticated cannot read private notes');
select throws_ok($$insert into knowledge.source_confidential values ('mp-privileges', 'client note')$$,
  '42501', null, 'authenticated cannot insert private notes');
select throws_ok($$update knowledge.source_confidential set licence_note = 'client revised'$$,
  '42501', null, 'authenticated cannot update private notes');
select throws_ok($$delete from knowledge.source_confidential$$,
  '42501', null, 'authenticated cannot delete private notes');
reset role;

set local role anon;
select throws_ok($$select licence_note from knowledge.source_confidential$$,
  '42501', null, 'anon cannot access private notes');
reset role;

select is(
  (select licence_note from knowledge.source_confidential where source_id = 'mp-privileges'),
  'admin revised', 'denied mutations did not change the admin note'
);
select lives_ok($$delete from knowledge.source_confidential where source_id = 'mp-privileges'$$,
  'admin ingestion can delete private notes');
select * from finish();
rollback;
