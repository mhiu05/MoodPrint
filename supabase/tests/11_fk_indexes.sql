begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

-- A cascade needs every FK column in an index prefix. A partial index excluding
-- null references is also sufficient: null references never participate in FKs.
select ok(exists (
  select 1 from pg_index i
  where i.indrelid=c.conrelid and i.indisvalid
    and (i.indpred is null or pg_get_expr(i.indpred,i.indrelid)=format('(%I IS NOT NULL)',
      (select attname from pg_attribute where attrelid=c.conrelid and attnum=c.conkey[1])))
    and (i.indkey::smallint[])[0:cardinality(c.conkey)-1] @> c.conkey
), format('%s has a covering index',c.conname))
from pg_constraint c
join pg_namespace n on n.oid=c.connamespace
where c.contype='f' and n.nspname in ('app','agent_store');

select * from finish();
rollback;
