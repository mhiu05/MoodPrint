-- Retrieval is metadata, not a new user-approved fact. In particular reading an
-- old memory must not make it look recently confirmed to the Context Builder.
-- Replace only these two triggers; other domain updated_at/version rules stay.
create or replace trigger user_memories_touch
before update on app.user_memories
for each row
when (
  row(old.owner_id,old.category,old.content,old.content_hash,old.status,
      old.supersedes_id,old.source_kind,old.source_candidate_id,
      old.source_conversation_id,old.expires_at)
  is distinct from
  row(new.owner_id,new.category,new.content,new.content_hash,new.status,
      new.supersedes_id,new.source_kind,new.source_candidate_id,
      new.source_conversation_id,new.expires_at)
)
execute function app_private.touch_updated_at();

create or replace trigger user_memories_version
before update on app.user_memories
for each row
when (
  row(old.owner_id,old.category,old.content,old.content_hash,old.status,
      old.supersedes_id,old.source_kind,old.source_candidate_id,
      old.source_conversation_id,old.expires_at)
  is distinct from
  row(new.owner_id,new.category,new.content,new.content_hash,new.status,
      new.supersedes_id,new.source_kind,new.source_candidate_id,
      new.source_conversation_id,new.expires_at)
)
execute function app_private.bump_version();
