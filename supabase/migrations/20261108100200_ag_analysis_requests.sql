-- Phase 3: consent-bound evidence analysis requests (idempotent by client id).
-- Identity, consent and digests are never updatable; only the outcome columns are.
create table app.analysis_requests (
  id uuid primary key,
  owner_id uuid not null,
  evidence_id uuid not null,
  consent_version text not null check(char_length(consent_version) between 1 and 80),
  consent_at timestamptz not null,
  status text not null default 'running' check(status in ('running','succeeded','failed','cancelled')),
  source_sha256 text not null check(char_length(source_sha256)=64 and translate(source_sha256,'0123456789abcdef','')=''),
  request_sha256 text not null check(char_length(request_sha256)=64 and translate(request_sha256,'0123456789abcdef','')=''),
  derivative_id uuid unique references app.evidence_derivatives(id) on delete set null,
  error_code text check(error_code is null or char_length(error_code)<=80),
  usage jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  check(id<>'00000000-0000-0000-0000-000000000000'),
  check((status='running')=(finished_at is null)),
  unique(id,owner_id),
  foreign key(evidence_id,owner_id) references app.evidence_items(id,owner_id) on delete cascade
);
create index analysis_requests_evidence_owner on app.analysis_requests(evidence_id,owner_id);
create index analysis_requests_owner_started on app.analysis_requests(owner_id,started_at desc);

alter table app.analysis_requests enable row level security;
create policy owner_select on app.analysis_requests for select to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
create policy owner_insert on app.analysis_requests for insert to authenticated
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status='running');
create policy owner_update on app.analysis_requests for update to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status='running')
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
grant select,insert on app.analysis_requests to authenticated;
grant update(status,derivative_id,error_code,usage,finished_at) on app.analysis_requests to authenticated;
