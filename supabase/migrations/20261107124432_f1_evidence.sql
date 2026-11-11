create table app.evidence_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  case_id uuid,
  kind text not null check(kind in ('image','audio','video','document','text_note','other')),
  origin text not null check(origin in ('user_upload','user_entered')),
  storage_bucket text,
  storage_key text unique,
  original_filename text,
  declared_mime_type text,
  stored_mime_type text,
  expected_byte_size bigint check(expected_byte_size>=0),
  byte_size bigint check(byte_size>=0),
  client_sha256 text check(client_sha256 is null or client_sha256 ~ '^[0-9a-f]{64}$'),
  storage_etag text,
  original_text text,
  shown_timestamp text not null default '',
  captured_at_label text not null default '',
  user_edited_text text,
  review_status text not null default 'unreviewed' check(review_status in ('unreviewed','corrected','confirmed','rejected')),
  limitations text[] not null default '{}',
  upload_status text not null default 'pending' check(upload_status in ('pending','uploaded','failed','deleting')),
  purge_claimed_at timestamptz,
  purged_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(case_id,owner_id) references app.cases(id,owner_id) on delete set null(case_id),
  check((kind='text_note' and origin='user_entered' and original_text is not null and storage_key is null and expected_byte_size is null)
     or (kind<>'text_note' and origin='user_upload' and storage_bucket is not distinct from 'incident-evidence' and storage_key is not null and expected_byte_size is not null)),
  check(storage_key is null or storage_key like 'users/' || owner_id::text || '/originals/' || id::text || '/%'),
  check(upload_status<>'uploaded' or kind='text_note' or (byte_size is not null and stored_mime_type is not null))
);
create index evidence_owner_case on app.evidence_items(owner_id,case_id);
create index evidence_case_owner on app.evidence_items(case_id,owner_id) where case_id is not null;
create index evidence_unlinked on app.evidence_items(owner_id) where case_id is null;
create index evidence_pending_purge on app.evidence_items(created_at) where upload_status in ('pending','deleting','failed');
alter table app.evidence_items enable row level security;
create policy owner_all on app.evidence_items for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.evidence_items to authenticated;
create trigger evidence_touch before update on app.evidence_items for each row execute function app_private.touch_updated_at();

create function app_private.guard_evidence_immutable() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if row(new.id,new.owner_id,new.kind,new.origin,new.storage_bucket,new.storage_key,
         new.original_filename,new.declared_mime_type,new.expected_byte_size,new.client_sha256,
         new.original_text,new.shown_timestamp,new.created_at)
     is distinct from row(old.id,old.owner_id,old.kind,old.origin,old.storage_bucket,old.storage_key,
         old.original_filename,old.declared_mime_type,old.expected_byte_size,old.client_sha256,
         old.original_text,old.shown_timestamp,old.created_at)
     or (old.byte_size is not null and new.byte_size is distinct from old.byte_size)
     or (old.stored_mime_type is not null and new.stored_mime_type is distinct from old.stored_mime_type)
     or (old.storage_etag is not null and new.storage_etag is distinct from old.storage_etag)
     or (old.upload_status='uploaded' and new.upload_status not in ('uploaded','deleting')) then
    raise exception 'Original evidence is immutable' using errcode='23514';
  end if;
  return new;
end $$;
revoke all on function app_private.guard_evidence_immutable() from public,anon,service_role;
grant execute on function app_private.guard_evidence_immutable() to authenticated;
create trigger evidence_immutable before update on app.evidence_items for each row execute function app_private.guard_evidence_immutable();

create table app.case_event_evidence (
  event_id uuid not null,
  evidence_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  primary key(event_id,evidence_id),
  foreign key(event_id,owner_id) references app.case_events(id,owner_id) on delete cascade,
  foreign key(evidence_id,owner_id) references app.evidence_items(id,owner_id) on delete cascade
);
create index case_event_evidence_event_owner on app.case_event_evidence(event_id,owner_id);
create index case_event_evidence_evidence_owner on app.case_event_evidence(evidence_id,owner_id);
create index case_event_evidence_owner on app.case_event_evidence(owner_id);
alter table app.case_event_evidence enable row level security;
create policy owner_all on app.case_event_evidence for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.case_event_evidence to authenticated;

create function app_private.guard_event_evidence_case() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if not exists(select 1 from app.case_events ev join app.evidence_items ei
    on ei.case_id=ev.case_id and ei.owner_id=ev.owner_id
    where ev.id=new.event_id and ei.id=new.evidence_id and ev.owner_id=new.owner_id) then
    raise exception 'Evidence must belong to the event case' using errcode='23514';
  end if;
  return new;
end $$;
revoke all on function app_private.guard_event_evidence_case() from public,anon,service_role;
grant execute on function app_private.guard_event_evidence_case() to authenticated;
create trigger event_evidence_case before insert or update on app.case_event_evidence
for each row execute function app_private.guard_event_evidence_case();

create table app.evidence_derivatives (
  id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check(kind in ('thumbnail','ocr_text','transcript','ai_analysis')),
  storage_key text,
  content jsonb,
  generator text not null,
  generator_version text not null,
  source_sha256 text,
  created_at timestamptz not null default now(),
  foreign key(evidence_id,owner_id) references app.evidence_items(id,owner_id) on delete cascade,
  check(storage_key is null or storage_key like 'users/' || owner_id::text || '/derived/' || evidence_id::text || '/' || kind || '/' || id::text || '%')
);
create index evidence_derivatives_evidence_owner on app.evidence_derivatives(evidence_id,owner_id);
create index evidence_derivatives_owner on app.evidence_derivatives(owner_id);
alter table app.evidence_derivatives enable row level security;
create policy owner_all on app.evidence_derivatives for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.evidence_derivatives to authenticated;

create function app_private.claim_evidence_for_purge(batch_size integer)
returns table(id uuid,storage_key text) language sql security definer set search_path='' as $$
  with candidates as (
    select e.id from app.evidence_items e
    where (e.upload_status='deleting' or (e.upload_status='failed' and e.purged_at is null)
      or (e.upload_status='pending' and e.created_at<now()-interval '48 hours'))
      and (e.purge_claimed_at is null or e.purge_claimed_at<now()-interval '5 minutes')
    order by e.created_at limit greatest(0,least(batch_size,100)) for update skip locked
  ), claimed as (
    update app.evidence_items e set purge_claimed_at=now(),
      upload_status=case when e.upload_status='deleting' then 'deleting' else 'failed' end
    from candidates c where e.id=c.id returning e.id,e.storage_key
  )
  select c.id,c.storage_key from claimed c
  union all select c.id,d.storage_key from claimed c
    join app.evidence_derivatives d on d.evidence_id=c.id where d.storage_key is not null;
$$;
create function app_private.finish_evidence_purge(evidence_id uuid) returns void
language plpgsql security definer set search_path='' as $$
begin
  delete from app.evidence_items e where e.id=evidence_id and e.upload_status='deleting';
  update app.evidence_items e set purged_at=now()
    where e.id=evidence_id and e.upload_status='failed' and e.purge_claimed_at is not null;
end $$;
revoke all on function app_private.claim_evidence_for_purge(integer),app_private.finish_evidence_purge(uuid)
from public,anon,authenticated,service_role;
grant execute on function app_private.claim_evidence_for_purge(integer),app_private.finish_evidence_purge(uuid) to safevoice_api;
