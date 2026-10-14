"""insert_record and update_record -- the guarded write path.

Every write is guarded by, in order:
  1. Pydantic shape validation (models.py).
  2. Policy authorization: table must be writable, and every column must
     be in that table's writable_columns allow-list.
  3. Dry-run by default: with confirm=False the tool reports exactly what
     it *would* do and changes nothing. Only confirm=True commits.
  4. A real transaction: the write and a verifying read happen inside one
     transaction that is rolled back on any error, so a half-written row
     can never be left behind.
  5. update_record must target exactly one row by primary key -- no bulk
     or unfiltered updates are possible.
"""

from __future__ import annotations

from pydantic import ValidationError

from guarded_mcp.app import mcp
from guarded_mcp.audit import audited
from guarded_mcp.db import get_write_pool
from guarded_mcp.models import InsertRequest, UpdateRequest
from guarded_mcp.policy import get_policy
from guarded_mcp.ratelimit import rate_limited


def _err(code: str, message: str, hint: str) -> dict:
    return {"error_code": code, "message": message, "hint": hint}


def _authorize_write(table: str, columns: set[str]):
    """Shared policy check for both write tools. Returns (table_policy, None)
    on success or (None, error_dict) on failure."""
    policy = get_policy()
    table_policy = policy.table(table)
    if table_policy is None or not table_policy.write:
        return None, _err(
            "TABLE_NOT_WRITABLE",
            f"Table '{table}' is not writable under the current policy.",
            f"Writable tables: {sorted(policy.writable_tables())}",
        )
    allowed = set(table_policy.writable_columns)
    disallowed = columns - allowed
    if disallowed:
        return None, _err(
            "COLUMN_NOT_WRITABLE",
            f"These columns may not be written: {sorted(disallowed)}",
            f"Writable columns for '{table}': {sorted(allowed)}",
        )
    return table_policy, None


@mcp.tool()
@audited("insert_record")
@rate_limited("insert_record", capacity=10, refill_per_second=0.5)
async def insert_record(table: str, values: dict, confirm: bool = False) -> dict:
    """Insert one row. Dry-run unless confirm=True.

    With confirm=False (default), returns the row that *would* be inserted
    without touching the database. Call again with confirm=True to commit.
    """
    try:
        req = InsertRequest(table=table, values=values, confirm=confirm)
    except ValidationError as e:
        return _err("VALIDATION_ERROR", str(e), "Check the argument shapes.")

    if not req.values:
        return _err("EMPTY_VALUES", "No values provided to insert.", "Pass a non-empty values dict.")

    table_policy, error = _authorize_write(req.table, set(req.values))
    if error:
        return error

    if not req.confirm:
        return {
            "dry_run": True,
            "would_insert": {"table": req.table, "values": req.values},
            "hint": "Call insert_record again with confirm=true to commit this.",
        }

    columns = list(req.values.keys())
    placeholders = [f"${i + 1}" for i in range(len(columns))]
    col_list = ", ".join(f'"{c}"' for c in columns)
    pk = table_policy.primary_key or "id"
    sql = (
        f'insert into "{req.table}" ({col_list}) '
        f'values ({", ".join(placeholders)}) returning "{pk}"'
    )

    pool = await get_write_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                new_id = await conn.fetchval(sql, *req.values.values())
    except Exception as e:
        # The transaction auto-rolls-back on this exception -- no partial row.
        return _err("INSERT_FAILED", str(e), "Check value types against describe_table.")

    return {"inserted": True, "table": req.table, "primary_key": {pk: new_id}}


@mcp.tool()
@audited("update_record")
@rate_limited("update_record", capacity=10, refill_per_second=0.5)
async def update_record(
    table: str, pk_value: object, changes: dict, confirm: bool = False
) -> dict:
    """Update exactly one row, identified by its primary key. Dry-run
    unless confirm=True.

    A missing/unknown primary key updates nothing and is reported as such
    -- there is no way to issue an unfiltered or multi-row UPDATE.
    """
    try:
        req = UpdateRequest(table=table, pk_value=pk_value, changes=changes, confirm=confirm)
    except ValidationError as e:
        return _err("VALIDATION_ERROR", str(e), "Check the argument shapes.")

    if not req.changes:
        return _err("EMPTY_CHANGES", "No changes provided.", "Pass a non-empty changes dict.")

    table_policy, error = _authorize_write(req.table, set(req.changes))
    if error:
        return error

    pk = table_policy.primary_key
    if not pk:
        return _err(
            "NO_PRIMARY_KEY",
            f"Table '{req.table}' has no primary_key defined in policy.",
            "Add a primary_key to this table in policy.yaml to allow updates.",
        )

    if not req.confirm:
        return {
            "dry_run": True,
            "would_update": {
                "table": req.table,
                "where": {pk: req.pk_value},
                "changes": req.changes,
            },
            "hint": "Call update_record again with confirm=true to commit this.",
        }

    set_cols = list(req.changes.keys())
    set_clause = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(set_cols))
    pk_placeholder = f"${len(set_cols) + 1}"
    sql = f'update "{req.table}" set {set_clause} where "{pk}" = {pk_placeholder}'

    pool = await get_write_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                status = await conn.execute(sql, *req.changes.values(), req.pk_value)
    except Exception as e:
        return _err("UPDATE_FAILED", str(e), "Check value types against describe_table.")

    # asyncpg returns e.g. "UPDATE 1" -- the trailing number is rows affected.
    affected = int(status.split()[-1])
    if affected == 0:
        return _err(
            "NO_ROW_MATCHED",
            f"No row in '{req.table}' has {pk} = {req.pk_value!r}. Nothing changed.",
            "Verify the primary key value with a query() first.",
        )
    return {"updated": True, "table": req.table, "rows_affected": affected}
