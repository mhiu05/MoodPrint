begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();
select has_table('app', name, format('Phase 1 table %s exists',name))
from unnest(array['cases','case_events','evidence_items','case_event_evidence',
  'evidence_derivatives','action_plans','plan_items','trusted_contacts',
  'support_drafts','knowledge_article_states','schools','school_memberships',
  'case_shares','case_share_evidence']) as name;
select has_function('app_private','is_school_member',array['uuid']);
select has_function('app_private','claim_evidence_for_purge',array['integer']);
select has_function('app_private','finish_evidence_purge',array['uuid']);
select has_function('app_private','shared_evidence_key',array['uuid','uuid','uuid']);
select has_function('app_private','own_upload_init_count',array[]::text[]);
select * from finish();
rollback;
