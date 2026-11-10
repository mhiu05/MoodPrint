-- Exact storage shape from openai-agents==0.24.0 SQLAlchemySession.
create table agent_store.agent_sessions (
  session_id varchar primary key,
  created_at timestamp not null default current_timestamp,
  updated_at timestamp not null default current_timestamp
);
create table agent_store.agent_messages (
  id serial primary key,
  session_id varchar not null references agent_store.agent_sessions(session_id) on delete cascade,
  message_data text not null,
  created_at timestamp not null default current_timestamp
);
create index idx_agent_messages_session_time on agent_store.agent_messages(session_id,created_at);
alter table agent_store.agent_sessions enable row level security;
alter table agent_store.agent_messages enable row level security;
create policy backend_all on agent_store.agent_sessions for all to moodprint_api using(true) with check(true);
create policy backend_all on agent_store.agent_messages for all to moodprint_api using(true) with check(true);
grant select,insert,update,delete on agent_store.agent_sessions,agent_store.agent_messages to moodprint_api;
grant usage,select on sequence agent_store.agent_messages_id_seq to moodprint_api;
