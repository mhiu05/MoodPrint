begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

select ok(c.relrowsecurity, format('%I has rls', c.relname))
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'knowledge' and c.relkind = 'r';

select ok(exists(select 1 from pg_policy p where p.polrelid = c.oid), format('%I has a policy', c.relname))
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'knowledge' and c.relkind = 'r';

select is(
  translate(
    normalize(lower('Đường đi bắt nạt ở trường'), nfd),
    chr(273)||chr(272)||chr(768)||chr(769)||chr(770)||chr(771)||chr(774)||chr(777)||chr(795)||chr(803),
    'dd'
  ),
  'duong di bat nat o truong',
  'folded school-bullying phrase'
);

select is(
  (select prosecdef from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'knowledge' and p.proname = 'published_version'),
  false,
  'published_version is security invoker'
);

select * from finish();
rollback;
