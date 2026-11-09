-- Knowledge corpus. Objects stay in schema knowledge.
-- licence_note is not a column of the publicly granted sources table:
-- frozen pgTAP 05_grants.sql requires table-level SELECT, and PostgreSQL
-- table SELECT cannot hide one column. Notes live in source_confidential.

create schema if not exists knowledge;

create table knowledge.corpus_versions (
  version text primary key check (
    length(version) = 14
    and substring(version from 1 for 3) = 'kb-'
    and substring(version from 12 for 1) = '-'
    and translate(substring(version from 4 for 8), '0123456789', '') = ''
    and translate(substring(version from 13 for 2), '0123456789', '') = ''
  ),
  status text not null check (status in ('building', 'validated', 'published', 'retired')),
  embedding_model text not null,
  embedding_dims integer not null check (embedding_dims = 1024),
  manifest_sha256 text not null check (
    length(manifest_sha256) = 64
    and translate(manifest_sha256, '0123456789abcdef', '') = ''
  ),
  builder text not null,
  stats jsonb not null default '{}'::jsonb,
  notes text not null default '',
  created_at timestamptz not null default now(),
  validated_at timestamptz,
  published_at timestamptz,
  retired_at timestamptz
);

create unique index corpus_one_published
  on knowledge.corpus_versions (status)
  where status = 'published';

create table knowledge.sources (
  source_id text primary key check (
    length(source_id) between 3 and 64
    and translate(source_id, 'abcdefghijklmnopqrstuvwxyz0123456789-', '') = ''
    and substring(source_id from 1 for 1) <> '-'
  ),
  kind text not null check (kind in ('law', 'guideline', 'report', 'factsheet', 'hotline', 'authored')),
  publisher text not null,
  title text not null,
  url text,
  language text not null,
  country_scope text[] not null check (cardinality(country_scope) > 0),
  authority_tier smallint not null check (authority_tier between 1 and 4),
  licence_class text not null check (licence_class in ('open_reuse', 'authored', 'reference_only')),
  licence_quote text,
  verified_on date not null,
  retrieved_on date,
  unique (source_id, licence_class)
);

create table knowledge.source_confidential (
  source_id text primary key references knowledge.sources (source_id) on delete cascade,
  licence_note text not null
);

comment on table knowledge.source_confidential is 'moodprint:private_ingestion';

create table knowledge.documents (
  corpus_version text not null references knowledge.corpus_versions (version) on delete cascade,
  document_id text not null check (
    length(document_id) between 3 and 96
    and translate(document_id, 'abcdefghijklmnopqrstuvwxyz0123456789._:-', '') = ''
  ),
  source_id text not null,
  source_licence_class text not null,
  licence_class text not null check (licence_class in ('open_reuse', 'authored')),
  check (licence_class = 'authored' or source_licence_class = 'open_reuse'),
  title text not null,
  language text not null,
  country_scope text[] not null,
  topics text[] not null default '{}',
  age_bands text[] not null default '{}',
  published_at date,
  last_reviewed date not null,
  applicability text not null,
  primary_url text,
  derived_from jsonb not null default '[]'::jsonb,
  legacy_article_id text,
  content_sha256 text not null,
  primary key (corpus_version, document_id),
  foreign key (source_id, source_licence_class)
    references knowledge.sources (source_id, licence_class)
);

create table knowledge.chunks (
  corpus_version text not null,
  document_id text not null,
  chunk_id text not null,
  ordinal integer not null check (ordinal >= 0),
  heading text not null default '',
  section_path text[] not null default '{}',
  text text not null check (length(text) between 40 and 2000),
  heading_norm text not null,
  fts tsvector not null,
  embedding vector(1024) not null,
  char_start integer,
  char_end integer,
  token_estimate integer not null,
  content_sha256 text not null,
  parser text not null,
  oversize boolean not null default false,
  primary key (corpus_version, chunk_id),
  unique (corpus_version, document_id, ordinal),
  foreign key (corpus_version, document_id)
    references knowledge.documents (corpus_version, document_id) on delete cascade
);

create index chunks_fts on knowledge.chunks using gin (fts);

create table knowledge.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  corpus_version text not null references knowledge.corpus_versions (version) on delete cascade,
  command text not null check (command in ('store', 'validate', 'publish', 'rollback')),
  status text not null check (status in ('started', 'succeeded', 'failed')),
  detail jsonb not null default '{}'::jsonb,
  git_commit text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create function knowledge.published_version()
returns text
language sql
stable
security invoker
as $$ select version from knowledge.corpus_versions where status = 'published' $$;

alter table knowledge.corpus_versions enable row level security;
alter table knowledge.sources enable row level security;
alter table knowledge.source_confidential enable row level security;
alter table knowledge.documents enable row level security;
alter table knowledge.chunks enable row level security;
alter table knowledge.ingestion_runs enable row level security;

create policy read_published on knowledge.corpus_versions
  for select to authenticated
  using (status = 'published');

create policy read_all on knowledge.sources
  for select to authenticated
  using (true);

create policy ingest_writer on knowledge.source_confidential
  for all to moodprint_api
  using (true)
  with check (true);

create policy read_published on knowledge.documents
  for select to authenticated
  using (corpus_version = knowledge.published_version());

create policy read_published on knowledge.chunks
  for select to authenticated
  using (corpus_version = knowledge.published_version());

create policy no_client_access on knowledge.ingestion_runs
  for select to authenticated
  using (false);

revoke all on schema knowledge from public;
revoke all on schema knowledge from anon;
grant usage on schema knowledge to authenticated;
grant usage on schema knowledge to moodprint_api;

revoke all on table knowledge.corpus_versions from public;
revoke all on table knowledge.corpus_versions from anon;
revoke all on table knowledge.sources from public;
revoke all on table knowledge.sources from anon;
revoke all on table knowledge.source_confidential from public;
revoke all on table knowledge.source_confidential from anon;
revoke all on table knowledge.source_confidential from authenticated;
revoke all on table knowledge.documents from public;
revoke all on table knowledge.documents from anon;
revoke all on table knowledge.chunks from public;
revoke all on table knowledge.chunks from anon;
revoke all on table knowledge.ingestion_runs from public;
revoke all on table knowledge.ingestion_runs from anon;

grant select on table knowledge.corpus_versions to authenticated;
grant select on table knowledge.sources to authenticated;
grant select on table knowledge.documents to authenticated;
grant select on table knowledge.chunks to authenticated;
grant select on table knowledge.ingestion_runs to authenticated;

grant insert on table knowledge.source_confidential to moodprint_api;
grant update on table knowledge.source_confidential to moodprint_api;
grant delete on table knowledge.source_confidential to moodprint_api;

revoke all on function knowledge.published_version() from public;
revoke all on function knowledge.published_version() from anon;
grant execute on function knowledge.published_version() to authenticated;
