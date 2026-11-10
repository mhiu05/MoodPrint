create table app.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nickname text not null check(char_length(nickname) between 2 and 32),
  age_band text check(age_band in ('11-13','14-17')),
  locale text not null default 'vi',
  start_interest text,
  reduced_motion boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table app.profiles enable row level security;
create policy owner_all on app.profiles for all to authenticated
using(user_id=(select auth.uid())) with check(user_id=(select auth.uid()));
grant select,insert,update,delete on app.profiles to authenticated;
create trigger profiles_touch before update on app.profiles for each row execute function app_private.touch_updated_at();

create table app.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references auth.users(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id uuid not null,
  school_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index audit_events_actor_created on app.audit_events(actor_id,created_at);
alter table app.audit_events enable row level security;
create policy actor_insert on app.audit_events for insert to authenticated
with check(actor_id=(select auth.uid()));
grant insert on app.audit_events to authenticated;
comment on column app.audit_events.metadata is 'Identifiers and operational metadata only. Never store user content.';
