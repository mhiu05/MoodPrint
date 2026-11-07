insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('incident-evidence','incident-evidence',false,null,null)
on conflict(id) do nothing;
do $$ begin
  if not exists(select 1 from storage.buckets where id='incident-evidence' and public=false and file_size_limit is null and allowed_mime_types is null) then
    raise exception 'incident-evidence bucket must be private with no bucket limits';
  end if;
end $$;
-- No user/anonymous storage.objects policy: signed credentials are issued only by backend.
