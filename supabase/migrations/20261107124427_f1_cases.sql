create table app.cases (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  title text not null default '' check(char_length(title)<=120),
  template text not null check(template in ('TPL-VERBAL','TPL-THREAT','TPL-EXCLUSION','TPL-PHYSICAL','TPL-IMAGE','TPL-IMPERSONATION','TPL-WITNESS','TPL-FREE')),
  perspective text not null default 'self' check(perspective in ('self','witness')),
  summary text not null default '',
  category_tags text[] not null default '{}',
  impact_tags text[] not null default '{}',
  status text not null default 'draft' check(status in ('draft','active','monitoring','closed')),
  people text not null default '',
  place text not null default '',
  occurred_label text not null default '',
  tried text not null default '',
  trusted_person text not null default '',
  search_text text generated always as (lower(app_private.f_unaccent(title || ' ' || summary))) stored,
  version integer not null default 1 check(version>=1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  check(status='draft' or (btrim(title)<>'' and btrim(summary)<>''))
);
create index cases_owner_updated on app.cases(owner_id,updated_at desc,id);
create index cases_owner_status on app.cases(owner_id,status);
create index cases_search on app.cases using gin(search_text extensions.gin_trgm_ops);
alter table app.cases enable row level security;
create policy owner_all on app.cases for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.cases to authenticated;
create trigger cases_touch before update on app.cases for each row execute function app_private.touch_updated_at();
create trigger cases_version before update on app.cases for each row execute function app_private.bump_version();

create table app.case_events (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  occurred_at timestamptz,
  occurred_on date,
  time_precision text not null default 'unknown' check(time_precision in ('exact','day','week','unknown')),
  place text not null default '',
  description text not null check(btrim(description)<>''),
  provenance text not null default 'user_entered' check(provenance in ('user_entered','ai_extracted','user_confirmed')),
  needs_review boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(case_id,owner_id) references app.cases(id,owner_id) on delete cascade,
  check((time_precision='exact' and occurred_at is not null and occurred_on is null)
    or (time_precision in ('day','week') and occurred_on is not null and occurred_at is null)
    or (time_precision='unknown' and occurred_at is null and occurred_on is null))
);
create index case_events_case_owner on app.case_events(case_id,owner_id,occurred_on,occurred_at);
create index case_events_owner on app.case_events(owner_id);
alter table app.case_events enable row level security;
create policy owner_all on app.case_events for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.case_events to authenticated;
create trigger case_events_touch before update on app.case_events for each row execute function app_private.touch_updated_at();

alter table app.conversations add constraint conversations_case_owner_fk
foreign key(linked_case_id,owner_id) references app.cases(id,owner_id) on delete set null(linked_case_id);
create index conversations_case_owner on app.conversations(linked_case_id,owner_id) where linked_case_id is not null;
