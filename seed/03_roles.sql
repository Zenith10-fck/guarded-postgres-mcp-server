-- Least-privilege role the MCP server actually connects as.
--
-- Even if every guard in the Python code had a bug, this role has no
-- permission to INSERT, UPDATE, DELETE, DROP, or ALTER anything -- the
-- database itself refuses those statements, independent of our
-- application-level SQL guard. This is "defense in depth": two
-- independent layers that both have to fail for a write to slip through.

create role guarded_reader login password 'guarded_reader_password';
grant connect on database guarded_demo to guarded_reader;
grant usage on schema public to guarded_reader;
grant select on leads, orders, invoices to guarded_reader;

-- Fase 3: a second, separate role for guarded writes. It can INSERT and
-- UPDATE the tables that policy.yaml marks writable -- but still cannot
-- DELETE, DROP, or ALTER anything. The read path keeps using
-- guarded_reader; only insert_record/update_record use this role. Keeping
-- them separate means a bug in the read path can never write, by
-- construction.
create role guarded_writer login password 'guarded_writer_password';
grant connect on database guarded_demo to guarded_writer;
grant usage on schema public to guarded_writer;
grant select, insert, update on leads to guarded_writer;
grant usage, select on sequence leads_id_seq to guarded_writer;

