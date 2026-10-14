"""list_tables and describe_table -- policy-filtered schema introspection."""

from guarded_mcp.app import mcp
from guarded_mcp.audit import audited
from guarded_mcp.db import get_pool
from guarded_mcp.policy import get_policy
from guarded_mcp.ratelimit import rate_limited
from guarded_mcp.redact import redact_row


@mcp.tool()
@audited("list_tables")
@rate_limited("list_tables", capacity=30, refill_per_second=2.0)
async def list_tables() -> list[str]:
    """List the tables Claude is allowed to see, per policy.yaml's allow-list."""
    policy = get_policy()
    return sorted(policy.readable_tables())


@mcp.tool()
@audited("describe_table")
@rate_limited("describe_table", capacity=30, refill_per_second=2.0)
async def describe_table(table: str) -> dict:
    """Describe one table: its allow-listed columns and a 3-row sample
    (with PII columns masked, per policy.yaml).

    Returns a structured error (never a stack trace) if `table` isn't in
    the policy's allow-list.
    """
    policy = get_policy()
    table_policy = policy.table(table)
    if table_policy is None or not table_policy.read:
        return {
            "error_code": "TABLE_NOT_ALLOWED",
            "message": f"Table '{table}' is not readable under the current policy.",
            "hint": f"Allowed tables: {sorted(policy.readable_tables())}",
        }

    pool = await get_pool()
    column_rows = await pool.fetch(
        """
        select column_name, data_type
        from information_schema.columns
        where table_schema = 'public' and table_name = $1
        order by ordinal_position
        """,
        table,
    )
    allowed_cols = set(table_policy.columns)
    columns = [
        {"name": r["column_name"], "type": r["data_type"]}
        for r in column_rows
        if r["column_name"] in allowed_cols
    ]

    # `table` is only safe to interpolate here because it was just checked
    # against an exact key in policy.tables (operator-authored, not
    # attacker-controlled) -- never do this with arbitrary user input.
    sample_rows = await pool.fetch(f'select * from "{table}" limit 3')
    pii_columns = set(table_policy.pii_columns)
    sample = [
        redact_row(
            {k: v for k, v in dict(r).items() if k in allowed_cols}, pii_columns
        )
        for r in sample_rows
    ]

    return {"table": table, "columns": columns, "sample_rows": sample}
