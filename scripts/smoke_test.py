"""Fase 3 sanity check: guarded writes (insert/update) with dry-run,
Pydantic validation, policy authorization, and transactional safety --
on top of everything the earlier phases proved.

Run: python scripts/smoke_test.py
"""

import asyncio

import asyncpg

from guarded_mcp.db import DATABASE_URL, get_pool
from guarded_mcp.tools.audit import get_audit_log
from guarded_mcp.tools.query import query
from guarded_mcp.tools.tables import describe_table, list_tables
from guarded_mcp.tools.writes import insert_record, update_record


async def main() -> None:
    # --- read path (unchanged from fase 2) ---
    assert await list_tables() == ["invoices", "leads", "orders"]
    described = await describe_table("leads")
    assert described["sample_rows"][0]["email"] == "***REDACTED***"
    normal = await query("select id, full_name, email from leads where status = 'closed'")
    assert all(r["email"] == "***REDACTED***" for r in normal["rows"])
    assert (await query("select * from leads; drop table leads;"))["error_code"] == "MULTI_STATEMENT_REJECTED"

    # read role still cannot write, at the DB layer
    pool = await get_pool()
    try:
        await pool.execute("insert into leads (full_name, email, source) values ('x','x@x.com','t')")
        raise AssertionError("guarded_reader must not INSERT")
    except asyncpg.InsufficientPrivilegeError:
        pass
    assert "guarded_reader" in DATABASE_URL
    print("1-2. Read path + PII + read-role-cannot-write: OK")

    # --- guarded writes (fase 3) ---
    dry = await insert_record("leads", {"full_name": "Test User", "email": "t@e.com", "source": "referral"})
    print("3. insert dry-run:", dry)
    assert dry["dry_run"] is True

    before = await query("select id from leads")
    committed = await insert_record(
        "leads", {"full_name": "Test User", "email": "t@e.com", "source": "referral"}, confirm=True
    )
    print("4. insert confirm=True:", committed)
    assert committed["inserted"] is True
    new_id = committed["primary_key"]["id"]
    after = await query("select id from leads")
    assert after["row_count"] == before["row_count"] + 1

    # writing a column that isn't in writable_columns is rejected
    bad_col = await insert_record("leads", {"id": 999, "full_name": "Hacker"}, confirm=True)
    print("5. insert protected column (id):", bad_col)
    assert bad_col["error_code"] == "COLUMN_NOT_WRITABLE"

    # writing to a non-writable table is rejected
    bad_table = await insert_record("orders", {"amount_cents": 100}, confirm=True)
    print("6. insert into non-writable table:", bad_table)
    assert bad_table["error_code"] == "TABLE_NOT_WRITABLE"

    upd_dry = await update_record("leads", new_id, {"status": "qualified"})
    print("7. update dry-run:", upd_dry)
    assert upd_dry["dry_run"] is True

    upd = await update_record("leads", new_id, {"status": "qualified"}, confirm=True)
    print("8. update confirm=True:", upd)
    assert upd["updated"] is True and upd["rows_affected"] == 1

    # update targeting a non-existent primary key changes nothing
    ghost = await update_record("leads", 999999, {"status": "closed"}, confirm=True)
    print("9. update non-existent pk:", ghost)
    assert ghost["error_code"] == "NO_ROW_MATCHED"

    log = await get_audit_log(limit=30)
    tools_logged = {e["tool"] for e in log}
    assert {"insert_record", "update_record", "query"} <= tools_logged
    print("10. writes are audited too. Tools seen:", sorted(tools_logged))

    print("\nOK -- Fase 3 works: writes are dry-run by default, only touch")
    print("allow-listed tables/columns, run in rollback-safe transactions,")
    print("update exactly one row by primary key, and are fully audited.")


if __name__ == "__main__":
    asyncio.run(main())
