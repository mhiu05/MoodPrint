create table app.conversations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  title text not null default '',
  linked_case_id uuid,
  source_article_id text,
  summary text,
  status text not null default 'active' check(status in ('active','archived')),
  last_message_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id)
);
create index conversations_owner_last_message on app.conversations(owner_id,last_message_at desc);
alter table app.conversations enable row level security;
create policy owner_all on app.conversations for all to authenticated
using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.conversations to authenticated;
create trigger conversations_touch before update on app.conversations for each row execute function app_private.touch_updated_at();

create table app.agent_runs (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'running' check(status in ('running','awaiting_approval','completed','failed','cancelled','interrupted')),
  model text not null,
  prompt_version text not null,
  tools_version text not null,
  input_tokens integer not null default 0 check(input_tokens>=0),
  output_tokens integer not null default 0 check(output_tokens>=0),
  total_tokens integer not null default 0 check(total_tokens>=0),
  request_count integer not null default 0 check(request_count>=0),
  tool_call_count integer not null default 0 check(tool_call_count>=0),
  latency_ms integer check(latency_ms>=0),
  error_code text,
  heartbeat_at timestamptz not null default now(),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  unique(id,owner_id),
  unique(id,conversation_id,owner_id),
  foreign key(conversation_id,owner_id) references app.conversations(id,owner_id) on delete cascade
);
create unique index agent_runs_one_active on app.agent_runs(conversation_id) where status in ('running','awaiting_approval');
create index agent_runs_owner_started on app.agent_runs(owner_id,started_at desc);
create index agent_runs_stale on app.agent_runs(heartbeat_at) where status='running';
alter table app.agent_runs enable row level security;
create policy owner_select on app.agent_runs for select to authenticated using(owner_id=(select auth.uid()));
create policy owner_insert on app.agent_runs for insert to authenticated with check(owner_id=(select auth.uid()));
create policy owner_update on app.agent_runs for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update on app.agent_runs to authenticated;

create table app.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  role text not null check(role in ('user','assistant','system')),
  content text not null,
  client_message_id uuid,
  run_id uuid,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  unique(id,owner_id),
  unique(conversation_id,client_message_id),
  foreign key(conversation_id,owner_id) references app.conversations(id,owner_id) on delete cascade,
  foreign key(run_id,conversation_id,owner_id) references app.agent_runs(id,conversation_id,owner_id) on delete set null(run_id)
);
create index messages_conversation_created on app.messages(conversation_id,created_at);
create index messages_owner on app.messages(owner_id);
create index messages_run_owner on app.messages(run_id,conversation_id,owner_id);
alter table app.messages enable row level security;
create policy owner_all on app.messages for all to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.messages to authenticated;

create table app.tool_approvals (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  tool_name text not null,
  tool_call_id text not null,
  arguments_preview jsonb not null,
  run_state text not null,
  status text not null default 'pending' check(status in ('pending','approved','rejected','expired')),
  decided_at timestamptz,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(run_id,tool_call_id),
  foreign key(run_id,owner_id) references app.agent_runs(id,owner_id) on delete cascade
);
create index tool_approvals_owner on app.tool_approvals(owner_id);
alter table app.tool_approvals enable row level security;
create policy owner_select on app.tool_approvals for select to authenticated using(owner_id=(select auth.uid()));
create policy owner_insert on app.tool_approvals for insert to authenticated with check(owner_id=(select auth.uid()));
create policy owner_update on app.tool_approvals for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update on app.tool_approvals to authenticated;
