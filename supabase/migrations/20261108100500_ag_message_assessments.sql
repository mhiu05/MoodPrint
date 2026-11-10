-- Phase 3: structured CompanionTurn output per assistant message. app.messages is a frozen
-- baseline table without a structured column, so assessments live in their own table.
create table app.message_assessments (
  message_id uuid primary key,
  owner_id uuid not null,
  run_id uuid not null,
  structured jsonb not null check(jsonb_typeof(structured)='object'),
  created_at timestamptz not null default now(),
  foreign key(message_id,owner_id) references app.messages(id,owner_id) on delete cascade,
  foreign key(run_id,owner_id) references app.agent_runs(id,owner_id) on delete cascade
);
create index message_assessments_message_owner on app.message_assessments(message_id,owner_id);
create index message_assessments_run_owner on app.message_assessments(run_id,owner_id);
alter table app.message_assessments enable row level security;
create policy owner_select on app.message_assessments for select to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
create policy owner_insert on app.message_assessments for insert to authenticated
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
grant select,insert on app.message_assessments to authenticated;
