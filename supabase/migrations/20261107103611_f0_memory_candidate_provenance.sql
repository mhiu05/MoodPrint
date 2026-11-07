-- An approved candidate must remain discoverable even if its edited content
-- deduplicates into a memory created through another candidate or by the user.
-- Keep this internal provenance link out of client write DTOs.
alter table app.memory_candidates add column approved_memory_id uuid;
alter table app.memory_candidates
  add constraint memory_candidates_approved_memory_owner_fk
  foreign key(approved_memory_id,owner_id)
  references app.user_memories(id,owner_id) on delete cascade;
create index memory_candidates_approved_memory_owner
  on app.memory_candidates(approved_memory_id,owner_id)
  where approved_memory_id is not null;

-- Existing canonical candidate provenance can be reconstructed without
-- guessing the target of a deduplicated/edited historical candidate.
update app.memory_candidates candidate
set approved_memory_id=memory.id
from app.user_memories memory
where memory.source_candidate_id=candidate.id and memory.owner_id=candidate.owner_id;
