-- Phase 3: which evidence items a user attached to a chat message (ids only, never content).
create table app.message_attachments (
  message_id uuid not null,
  owner_id uuid not null,
  evidence_id uuid not null,
  created_at timestamptz not null default now(),
  primary key(message_id,evidence_id),
  foreign key(message_id,owner_id) references app.messages(id,owner_id) on delete cascade,
  foreign key(evidence_id,owner_id) references app.evidence_items(id,owner_id) on delete cascade
);
create index message_attachments_message_owner on app.message_attachments(message_id,owner_id);
create index message_attachments_evidence_owner on app.message_attachments(evidence_id,owner_id);
alter table app.message_attachments enable row level security;
create policy owner_select on app.message_attachments for select to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
create policy owner_insert on app.message_attachments for insert to authenticated
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
grant select,insert on app.message_attachments to authenticated;
