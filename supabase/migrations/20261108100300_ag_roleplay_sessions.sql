-- Phase 3: multi-turn roleplay practice sessions bound one-to-one to a conversation.
-- The scenario is fixed at creation; only progress columns are updatable, and only while active.
create table app.roleplay_sessions (
  id uuid primary key,
  owner_id uuid not null,
  conversation_id uuid not null unique,
  role text not null check(role in ('teacher','parent','trusted_adult')),
  scenario_key text not null check(char_length(scenario_key) between 1 and 80),
  scenario_context text not null default '' check(char_length(scenario_context)<=800),
  user_goal text not null default '' check(char_length(user_goal)<=300),
  difficulty smallint not null default 1 check(difficulty between 1 and 3),
  age_band text check(age_band is null or char_length(age_band)<=20),
  use_case_context boolean not null default false,
  linked_case_id uuid,
  status text not null default 'active' check(status in ('active','completed','abandoned')),
  turn_count integer not null default 0 check(turn_count>=0),
  safety_locked boolean not null default false,
  feedback jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  check(id<>'00000000-0000-0000-0000-000000000000'),
  check((status='active')=(completed_at is null)),
  unique(id,owner_id),
  foreign key(conversation_id,owner_id) references app.conversations(id,owner_id) on delete cascade,
  foreign key(linked_case_id,owner_id) references app.cases(id,owner_id) on delete set null(linked_case_id)
);
create index roleplay_sessions_conversation_owner on app.roleplay_sessions(conversation_id,owner_id);
create index roleplay_sessions_case_owner on app.roleplay_sessions(linked_case_id,owner_id) where linked_case_id is not null;
create index roleplay_sessions_owner_created on app.roleplay_sessions(owner_id,created_at desc);

alter table app.roleplay_sessions enable row level security;
create policy owner_select on app.roleplay_sessions for select to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
create policy owner_insert on app.roleplay_sessions for insert to authenticated
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status='active' and turn_count=0 and feedback is null);
create policy owner_update on app.roleplay_sessions for update to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status='active')
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
grant select,insert on app.roleplay_sessions to authenticated;
grant update(status,turn_count,safety_locked,feedback,completed_at) on app.roleplay_sessions to authenticated;
