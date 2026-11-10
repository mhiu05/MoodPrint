create table app.action_plans (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null unique,
  owner_id uuid not null references auth.users(id) on delete cascade,
  goal text not null default '',
  chosen_option_id text not null default '',
  status text not null default 'draft' check(status in ('draft','active','paused','completed')),
  next_review_date date,
  outcome_notes text not null default '',
  version integer not null default 1 check(version>=1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,owner_id),
  foreign key(case_id,owner_id) references app.cases(id,owner_id) on delete cascade,
  check(status='draft' or btrim(goal)<>'')
);
create index action_plans_case_owner on app.action_plans(case_id,owner_id);
create index action_plans_owner_updated on app.action_plans(owner_id,updated_at desc);

create table app.plan_items (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  label text not null check(btrim(label)<>''),
  status text not null default 'not_started' check(status in ('not_started','doing','done')),
  notes text not null default '',
  priority text not null default 'normal' check(priority in ('high','normal')),
  reason text not null default '',
  position integer not null check(position>=0),
  foreign key(plan_id,owner_id) references app.action_plans(id,owner_id) on delete cascade,
  unique(plan_id,position) deferrable initially deferred
);
create index plan_items_plan_owner on app.plan_items(plan_id,owner_id);
create index plan_items_owner on app.plan_items(owner_id);

create table app.trusted_contacts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  label text not null check(char_length(btrim(label)) between 2 and 80),
  role text not null check(char_length(btrim(role)) between 2 and 40),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index trusted_contacts_owner on app.trusted_contacts(owner_id,created_at);

create table app.support_drafts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  case_id uuid,
  recipient_type text not null default '',
  identity_mode text not null default 'alias' check(identity_mode in ('alias','disclose')),
  content text not null default '',
  compose jsonb not null default '{}',
  status text not null default 'draft' check(status in ('draft','prepared')),
  version integer not null default 1 check(version>=1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key(case_id,owner_id) references app.cases(id,owner_id) on delete set null(case_id)
);
create index support_drafts_owner on app.support_drafts(owner_id,updated_at desc);
create index support_drafts_case_owner on app.support_drafts(case_id,owner_id) where case_id is not null;

create table app.knowledge_article_states (
  owner_id uuid not null references auth.users(id) on delete cascade,
  article_id text not null check(char_length(article_id) between 1 and 120),
  bookmarked boolean not null default false,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(owner_id,article_id)
);

do $$ declare table_name text; begin
  foreach table_name in array array['action_plans','plan_items','trusted_contacts','support_drafts','knowledge_article_states'] loop
    execute format('alter table app.%I enable row level security',table_name);
    execute format('create policy owner_all on app.%I for all to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()))',table_name);
    execute format('grant select,insert,update,delete on app.%I to authenticated',table_name);
    if table_name<>'plan_items' then
      execute format('create trigger %I before update on app.%I for each row execute function app_private.touch_updated_at()',table_name||'_touch',table_name);
    end if;
    if table_name in ('action_plans','support_drafts') then
      execute format('create trigger %I before update on app.%I for each row execute function app_private.bump_version()',table_name||'_version',table_name);
    end if;
  end loop;
end $$;
