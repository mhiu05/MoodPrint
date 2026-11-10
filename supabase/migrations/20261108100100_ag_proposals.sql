-- Phase 3: immutable server-side proposals for Companion write tools.
-- The model can only ever send a proposal_id; the stored payload is what the user approved.
--
-- Scope note: the migration scope checker allows only app/agent_store references and SQL-language
-- functions, so enforcement here uses column-level grants (content can never be updated), RLS
-- (terminal rows are frozen, new status values are restricted) and CHECK constraints. The
-- remaining state-machine rules (legal transitions, write-once binding, binding backed by an
-- approved tool approval, expiry) are enforced by ProposalStore compare-and-set updates; see
-- docs/implementation/compat/CC-P3-001.md for the proposed trigger-based hardening.
create table app.agent_proposals (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  conversation_id uuid not null,
  run_id uuid not null,
  kind text not null check(kind in ('case_event','action_plan')),
  target_case_id uuid not null,
  payload jsonb not null,
  payload_sha256 text not null check(char_length(payload_sha256)=64 and translate(payload_sha256,'0123456789abcdef','')=''),
  preview jsonb not null,
  base_version integer check(base_version is null or base_version>=1),
  request_key text not null check(char_length(request_key) between 1 and 200),
  approval_binding jsonb,
  status text not null default 'proposed' check(status in ('proposed','approved','rejected','applied','expired','failed')),
  result jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  decided_at timestamptz,
  applied_at timestamptz,
  check(id<>'00000000-0000-0000-0000-000000000000'),
  check(expires_at>created_at),
  check(jsonb_typeof(payload)='object' and jsonb_typeof(preview)='object'),
  check(approval_binding is null or jsonb_typeof(approval_binding)='object'),
  check(approval_binding is null or approval_binding->>'payload_sha256'=payload_sha256),
  check(approval_binding is null or approval_binding->>'decision'='approve'),
  check(status not in ('approved','applied') or approval_binding is not null),
  check(status not in ('approved','rejected') or decided_at is not null),
  check(status<>'applied' or (applied_at is not null and result is not null)),
  unique(id,owner_id),
  unique(owner_id,run_id,request_key),
  foreign key(conversation_id,owner_id) references app.conversations(id,owner_id) on delete cascade,
  foreign key(run_id,owner_id) references app.agent_runs(id,owner_id) on delete cascade,
  foreign key(target_case_id,owner_id) references app.cases(id,owner_id) on delete cascade
);
create index agent_proposals_conversation_owner on app.agent_proposals(conversation_id,owner_id);
create index agent_proposals_case_owner on app.agent_proposals(target_case_id,owner_id);
create index agent_proposals_owner_status on app.agent_proposals(owner_id,status);

alter table app.agent_proposals enable row level security;
create policy owner_select on app.agent_proposals for select to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid));
create policy owner_insert on app.agent_proposals for insert to authenticated
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status='proposed' and approval_binding is null and result is null and decided_at is null and applied_at is null);
create policy owner_update on app.agent_proposals for update to authenticated
  using(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status in ('proposed','approved'))
  with check(owner_id=(select ((nullif(current_setting('request.jwt.claims',true),'')::jsonb)->>'sub')::uuid)
    and status in ('approved','rejected','expired','failed','applied'));
grant select,insert on app.agent_proposals to authenticated;
grant update(status,approval_binding,result,decided_at,applied_at) on app.agent_proposals to authenticated;
