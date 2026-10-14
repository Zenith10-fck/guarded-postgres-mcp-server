"""The adversarial attack catalog.

Each entry is one thing a careless (or malicious) caller might try to get
the server to do. `expect_error_code` is the structured error the server
MUST return instead of doing it. This is the single source of truth for
both the pytest suite and the results.json report -- add an attack here
and it shows up in both.
"""

# (name, category, tool, kwargs, expected error_code)
QUERY_ATTACKS = [
    ("drop_table", "ddl", "query", {"sql": "DROP TABLE leads"}, "NON_SELECT_REJECTED"),
    ("truncate_table", "ddl", "query", {"sql": "TRUNCATE leads"}, "NON_SELECT_REJECTED"),
    ("alter_table", "ddl", "query", {"sql": "ALTER TABLE leads ADD COLUMN x int"}, "NON_SELECT_REJECTED"),
    ("delete_rows", "dml", "query", {"sql": "DELETE FROM leads"}, "NON_SELECT_REJECTED"),
    ("update_rows", "dml", "query", {"sql": "UPDATE leads SET status='x'"}, "NON_SELECT_REJECTED"),
    ("insert_rows", "dml", "query", {"sql": "INSERT INTO leads(full_name) VALUES('x')"}, "NON_SELECT_REJECTED"),
    ("stacked_drop", "injection", "query", {"sql": "SELECT 1 FROM leads; DROP TABLE leads;"}, "MULTI_STATEMENT_REJECTED"),
    ("comment_smuggle", "injection", "query", {"sql": "SELECT * FROM leads -- ' OR 1=1"}, "COMMENT_REJECTED"),
    ("block_comment", "injection", "query", {"sql": "SELECT * FROM leads /* x */"}, "COMMENT_REJECTED"),
    ("cte_write", "injection", "query", {"sql": "WITH x AS (DELETE FROM leads RETURNING *) SELECT * FROM x"}, "FORBIDDEN_CLAUSE"),
    ("system_table", "exfiltration", "query", {"sql": "SELECT * FROM pg_catalog.pg_user"}, "TABLE_NOT_ALLOWED"),
    ("unlisted_table", "exfiltration", "query", {"sql": "SELECT * FROM information_schema.columns"}, "TABLE_NOT_ALLOWED"),
    ("select_into", "injection", "query", {"sql": "SELECT * INTO evil FROM leads"}, "FORBIDDEN_CLAUSE"),
]

WRITE_ATTACKS = [
    ("insert_protected_pk", "authorization", "insert_record", {"table": "leads", "values": {"id": 1, "full_name": "x"}, "confirm": True}, "COLUMN_NOT_WRITABLE"),
    ("insert_readonly_table", "authorization", "insert_record", {"table": "orders", "values": {"amount_cents": 1}, "confirm": True}, "TABLE_NOT_WRITABLE"),
    ("insert_unknown_table", "authorization", "insert_record", {"table": "secrets", "values": {"x": 1}, "confirm": True}, "TABLE_NOT_WRITABLE"),
    ("update_readonly_table", "authorization", "update_record", {"table": "invoices", "pk_value": 1, "changes": {"paid": True}, "confirm": True}, "TABLE_NOT_WRITABLE"),
    ("update_protected_col", "authorization", "update_record", {"table": "leads", "pk_value": 1, "changes": {"created_at": "2020-01-01"}, "confirm": True}, "COLUMN_NOT_WRITABLE"),
    ("update_ghost_row", "integrity", "update_record", {"table": "leads", "pk_value": 999999, "changes": {"status": "x"}, "confirm": True}, "NO_ROW_MATCHED"),
]

ALL_ATTACKS = QUERY_ATTACKS + WRITE_ATTACKS
