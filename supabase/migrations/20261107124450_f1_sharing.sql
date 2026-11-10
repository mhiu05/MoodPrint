create table app.schools (
  id uuid primary key default gen_random_uuid(),
  name text not null check(btrim(name)<>''),
  verification_status text not null check(verification_status in ('synthetic','verified')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table app.school_memberships (
  school_id uuid not null references app.schools(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check(role in ('staff','lead')),
  status text not null default 'active' check(status in ('active','inactive')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(school_id,user_id)
);
create index school_memberships_user on app.school_memberships(user_id);
alter table app.schools enable row level security;
alter table app.school_memberships enable row level security;

create function app_private.is_school_member(p_school_id uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select (select auth.uid()) is not null and exists(select 1 from app.school_memberships m
    where m.school_id=p_school_id and m.user_id=(select auth.uid()) and m.status='active');
$$;
revoke all on function app_private.is_school_member(uuid) from public,anon,service_role;
grant execute on function app_private.is_school_member(uuid) to authenticated;
create policy eligible_school on app.schools for select to authenticated
using(verification_status='verified' or app_private.is_school_member(id));
create policy own_membership on app.school_memberships for select to authenticated
using(user_id=(select auth.uid()));
grant select on app.schools,app.school_memberships to authenticated;

create table app.case_shares (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  case_id uuid,
  school_id uuid not null references app.schools(id) on delete restrict,
  status text not null default 'draft' check(status in ('draft','submitted','in_review','closed','withdrawn')),
  identity_mode text not null default 'alias' check(identity_mode in ('alias','disclose')),
  shared_fields text[] not null default '{}' check(shared_fields <@ array['title','summary','occurredAt','place','events','people','impactTags','tried']::text[]),
  snapshot jsonb,
  confirmation_version text,
  confirmed_at timestamptz,
  submitted_at timestamptz,
  withdrawn_at timestamptz,
  version integer not null default 1 check(version>=1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(case_id,owner_id) references app.cases(id,owner_id) on delete set null(case_id),
  check((status='draft' and snapshot is null and confirmed_at is null and submitted_at is null)
    or (status='withdrawn' and snapshot is null and withdrawn_at is not null)
    or (status in ('submitted','in_review','closed') and snapshot is not null
      and confirmation_version is not null and confirmed_at is not null and submitted_at is not null))
);
create unique index case_shares_one_active on app.case_shares(case_id,school_id) where status in ('draft','submitted','in_review');
create index case_shares_owner on app.case_shares(owner_id,created_at desc);
create index case_shares_school on app.case_shares(school_id,status);
create index case_shares_case_owner on app.case_shares(case_id,owner_id) where case_id is not null;
alter table app.case_shares enable row level security;
create policy owner_read on app.case_shares for select to authenticated using(owner_id=(select auth.uid()));
create policy owner_insert on app.case_shares for insert to authenticated with check(owner_id=(select auth.uid()) and status='draft');
create policy owner_update on app.case_shares for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
create policy staff_read on app.case_shares for select to authenticated
using(status in ('submitted','in_review','closed') and app_private.is_school_member(school_id));
grant select,insert,update on app.case_shares to authenticated;
create trigger case_shares_touch before update on app.case_shares for each row execute function app_private.touch_updated_at();
create trigger case_shares_version before update on app.case_shares for each row execute function app_private.bump_version();

create function app_private.guard_share_snapshot() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  if new.id is distinct from old.id or new.owner_id is distinct from old.owner_id then
    raise exception 'Share identity is immutable' using errcode='23514';
  end if;
  if old.status<>'draft' then
    if new.school_id is distinct from old.school_id or new.identity_mode is distinct from old.identity_mode
      or new.shared_fields is distinct from old.shared_fields
      or new.confirmation_version is distinct from old.confirmation_version
      or new.confirmed_at is distinct from old.confirmed_at
      or new.submitted_at is distinct from old.submitted_at
      or (new.case_id is distinct from old.case_id and new.case_id is not null)
      or (new.status<>'withdrawn' and new.snapshot is distinct from old.snapshot)
      or (old.status='withdrawn' and new.status<>'withdrawn') then
      raise exception 'Submitted share snapshot is immutable' using errcode='23514';
    end if;
  end if;
  return new;
end $$;
revoke all on function app_private.guard_share_snapshot() from public,anon,service_role;
grant execute on function app_private.guard_share_snapshot() to authenticated;
create trigger case_shares_guard before update on app.case_shares for each row execute function app_private.guard_share_snapshot();

create table app.case_share_evidence (
  share_id uuid not null,
  evidence_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  primary key(share_id,evidence_id),
  foreign key(share_id,owner_id) references app.case_shares(id,owner_id) on delete cascade,
  foreign key(evidence_id,owner_id) references app.evidence_items(id,owner_id) on delete cascade
);
create index case_share_evidence_share_owner on app.case_share_evidence(share_id,owner_id);
create index case_share_evidence_evidence_owner on app.case_share_evidence(evidence_id,owner_id);
create index case_share_evidence_owner on app.case_share_evidence(owner_id);
alter table app.case_share_evidence enable row level security;
create policy owner_all on app.case_share_evidence for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
create policy staff_read on app.case_share_evidence for select to authenticated using(exists(
  select 1 from app.case_shares s where s.id=share_id and s.status in ('submitted','in_review','closed')
    and app_private.is_school_member(s.school_id)));
grant select,insert,update,delete on app.case_share_evidence to authenticated;

create function app_private.guard_share_selection() returns trigger
language plpgsql security invoker set search_path='' as $$
declare share_status text; share_case uuid;
begin
  select s.status,s.case_id into share_status,share_case from app.case_shares s
    where s.id=case when tg_op='DELETE' then old.share_id else new.share_id end for update;
  if tg_op='DELETE' then
    if share_status is not null and share_status not in ('draft','withdrawn')
      and exists(select 1 from app.evidence_items e where e.id=old.evidence_id) then
      raise exception 'Submitted selection is immutable' using errcode='23514';
    end if;
    return old;
  end if;
  if share_status is distinct from 'draft' or not exists(select 1 from app.evidence_items e
    where e.id=new.evidence_id and e.owner_id=new.owner_id and e.case_id=share_case and e.upload_status='uploaded') then
    raise exception 'Select uploaded evidence in the draft case' using errcode='23514';
  end if;
  return new;
end $$;
revoke all on function app_private.guard_share_selection() from public,anon,service_role;
grant execute on function app_private.guard_share_selection() to authenticated;
create trigger share_evidence_guard before insert or update or delete on app.case_share_evidence
for each row execute function app_private.guard_share_selection();

create function app_private.shared_evidence_key(p_school_id uuid,p_share_id uuid,p_evidence_id uuid)
returns text language sql stable security definer set search_path='' as $$
  select e.storage_key from app.case_shares s
  join app.case_share_evidence se on se.share_id=s.id and se.owner_id=s.owner_id
  join app.evidence_items e on e.id=se.evidence_id and e.owner_id=se.owner_id
  where (select auth.uid()) is not null and s.id=p_share_id and s.school_id=p_school_id
    and e.id=p_evidence_id and e.upload_status='uploaded'
    and s.status in ('submitted','in_review','closed')
    and exists(select 1 from app.school_memberships m where m.school_id=s.school_id
      and m.user_id=(select auth.uid()) and m.status='active');
$$;
revoke all on function app_private.shared_evidence_key(uuid,uuid,uuid) from public,anon,service_role;
grant execute on function app_private.shared_evidence_key(uuid,uuid,uuid) to authenticated;

create function app_private.prepare_case_delete() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  update app.case_shares s set status='withdrawn',snapshot=null,withdrawn_at=now()
    where s.case_id=old.id and s.owner_id=old.owner_id and s.status<>'withdrawn';
  delete from app.case_share_evidence se using app.case_shares s
    where se.share_id=s.id and s.case_id=old.id and s.owner_id=old.owner_id;
  update app.evidence_items e set upload_status='deleting',purge_claimed_at=null
    where e.case_id=old.id and e.owner_id=old.owner_id;
  return old;
end $$;
revoke all on function app_private.prepare_case_delete() from public,anon,service_role;
grant execute on function app_private.prepare_case_delete() to authenticated;
create trigger cases_prepare_delete before delete on app.cases for each row execute function app_private.prepare_case_delete();
