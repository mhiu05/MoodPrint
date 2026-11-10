create table app.memory_candidates (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  category text not null check(category in ('preference','communication','support_person','goal','context')),
  content text not null check(char_length(content) between 1 and 500),
  source_kind text not null check(source_kind in ('user_explicit','agent_proposed')),
  source_conversation_id uuid,
  source_message_id uuid,
  supersedes_memory_id uuid,
  status text not null default 'pending' check(status in ('pending','approved','rejected','expired')),
  expires_at timestamptz not null default (now()+interval '30 days'),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(source_conversation_id,owner_id) references app.conversations(id,owner_id) on delete set null(source_conversation_id),
  foreign key(source_message_id,owner_id) references app.messages(id,owner_id) on delete set null(source_message_id)
);
create index memory_candidates_owner_status on app.memory_candidates(owner_id,status,created_at);
create index memory_candidates_source_conversation on app.memory_candidates(source_conversation_id,owner_id);
create index memory_candidates_source_message on app.memory_candidates(source_message_id,owner_id);
alter table app.memory_candidates enable row level security;
create policy owner_all on app.memory_candidates for all to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.memory_candidates to authenticated;
create trigger memory_candidates_touch before update on app.memory_candidates for each row execute function app_private.touch_updated_at();

create table app.user_memories (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  category text not null check(category in ('preference','communication','support_person','goal','context')),
  content text not null check(char_length(content) between 1 and 500),
  content_hash text not null,
  status text not null default 'active' check(status in ('active','superseded')),
  supersedes_id uuid,
  source_kind text not null check(source_kind in ('user_created','approved_candidate')),
  source_candidate_id uuid,
  source_conversation_id uuid,
  last_retrieved_at timestamptz,
  expires_at timestamptz,
  version integer not null default 1 check(version>=1),
  search tsvector generated always as (to_tsvector('simple'::regconfig,app_private.f_unaccent(content))) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(supersedes_id,owner_id) references app.user_memories(id,owner_id) on delete set null(supersedes_id),
  foreign key(source_candidate_id,owner_id) references app.memory_candidates(id,owner_id) on delete set null(source_candidate_id),
  foreign key(source_conversation_id,owner_id) references app.conversations(id,owner_id) on delete set null(source_conversation_id)
);
alter table app.memory_candidates add constraint memory_candidates_supersedes_fk foreign key(supersedes_memory_id,owner_id) references app.user_memories(id,owner_id) on delete set null(supersedes_memory_id);
create unique index user_memories_active_content on app.user_memories(owner_id,content_hash) where status='active';
create index user_memories_search on app.user_memories using gin(search);
create index user_memories_trigram on app.user_memories using gin(app_private.f_unaccent(content) extensions.gin_trgm_ops);
create index user_memories_owner_status_updated on app.user_memories(owner_id,status,updated_at desc);
create index user_memories_supersedes on app.user_memories(supersedes_id,owner_id);
create index user_memories_source_candidate on app.user_memories(source_candidate_id,owner_id);
create index user_memories_source_conversation on app.user_memories(source_conversation_id,owner_id);
create index memory_candidates_supersedes on app.memory_candidates(supersedes_memory_id,owner_id);
alter table app.user_memories enable row level security;
create policy owner_all on app.user_memories for all to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));
grant select,insert,update,delete on app.user_memories to authenticated;
create trigger user_memories_touch before update on app.user_memories for each row execute function app_private.touch_updated_at();
create trigger user_memories_version before update on app.user_memories for each row execute function app_private.bump_version();
