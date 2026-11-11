begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

-- The transaction rolls these deletes back. They keep the assertions independent of a seeded corpus.
delete from knowledge.chunks;
delete from knowledge.documents;
delete from knowledge.ingestion_runs;
delete from knowledge.source_confidential;
delete from knowledge.sources;
delete from knowledge.corpus_versions;

insert into knowledge.corpus_versions (version, status, embedding_model, embedding_dims, manifest_sha256, builder)
values
  ('kb-20261108-01', 'published', 'hashing', 1024, repeat('a', 64), 'pgtap'),
  ('kb-20261108-02', 'building', 'hashing', 1024, repeat('b', 64), 'pgtap');

insert into knowledge.sources (source_id, kind, publisher, title, language, country_scope, authority_tier, licence_class, licence_quote, verified_on)
values ('mp-pgtap', 'authored', 'SafeVoice', 'pgTAP', 'vi', array['VN'], 4, 'authored', 'test', '2026-11-08');

insert into knowledge.source_confidential (source_id, licence_note) values ('mp-pgtap', 'private note');

insert into knowledge.documents (
  corpus_version, document_id, source_id, source_licence_class, licence_class, title, language,
  country_scope, topics, age_bands, last_reviewed, applicability, content_sha256
) values
  ('kb-20261108-01', 'doc-pub', 'mp-pgtap', 'authored', 'authored', 'Public', 'vi', array['VN'], array['support'], array['11-13'], '2026-11-08', 'test', repeat('c', 64)),
  ('kb-20261108-02', 'doc-build', 'mp-pgtap', 'authored', 'authored', 'Hidden', 'vi', array['VN'], array['support'], array['11-13'], '2026-11-08', 'test', repeat('d', 64));

insert into knowledge.chunks (
  corpus_version, document_id, chunk_id, ordinal, heading, text, heading_norm, fts, embedding,
  token_estimate, content_sha256, parser
) values
  ('kb-20261108-01', 'doc-pub', 'pub-chunk', 0, 'Đường', repeat('ho tro ', 8), 'duong', to_tsvector('simple', 'ho tro'), ('[' || repeat('0,', 1023) || '0]')::vector, 20, repeat('e', 64), 'pgtap'),
  ('kb-20261108-02', 'doc-build', 'build-chunk', 0, 'Ẩn', repeat('an ', 20), 'an', to_tsvector('simple', 'an'), ('[' || repeat('0,', 1023) || '0]')::vector, 20, repeat('f', 64), 'pgtap');

set local role anon;
select throws_ok('select source_id from knowledge.sources', '42501', null, 'anon cannot read sources');
reset role;

set local role authenticated;
select results_eq('select document_id from knowledge.documents order by document_id', array['doc-pub']::text[], 'authenticated sees only the published document');
select throws_ok('insert into knowledge.sources (source_id, kind, publisher, title, language, country_scope, authority_tier, licence_class, verified_on) values (''nope'', ''authored'', ''x'', ''x'', ''vi'', array[''VN''], 4, ''authored'', ''2026-11-08'')', '42501', null, 'authenticated cannot insert');
select throws_ok('select licence_note from knowledge.source_confidential', '42501', null, 'licence note is not readable');
select is_empty('select * from knowledge.ingestion_runs', 'ingestion runs are hidden');
reset role;

select throws_ok(
  $$insert into knowledge.corpus_versions (version, status, embedding_model, embedding_dims, manifest_sha256, builder)
    values ('kb-20261108-03', 'published', 'hashing', 1024, repeat('c', 64), 'pgtap')$$,
  '23505',
  null,
  'only one published version'
);

select * from finish();
rollback;
