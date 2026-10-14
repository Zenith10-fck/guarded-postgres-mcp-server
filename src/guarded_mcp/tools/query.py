"""The `query` tool -- the guarded read path into the database."""

import asyncio

from guarded_mcp.app import mcp
from guarded_mcp.audit import audited
from guarded_mcp.db import get_pool
from guarded_mcp.policy import get_policy
from guarded_mcp.ratelimit import rate_limited
from guarded_mcp.redact import redact_rows
from guarded_mcp.sqlguard import SqlGuardError, guard_select


@mcp.tool()
@audited("query")
@rate_limited("query", capacity=20, refill_per_second=1.0)
async def query(sql: str) -> dict:
    """Run a single read-only SELECT against the allow-listed tables.

    Guardrails (see sqlguard.py): exactly one SELECT statement, no
    comments, no DDL/DML anywhere in the statement (including inside
    CTEs), only allow-listed tables, and a hard-enforced LIMIT. PII
    columns (per policy.yaml) are masked in the result. Failures return
    {error_code, message, hint} -- never a raw exception.
    """
    policy = get_policy()

    try:
        safe_sql, limit, referenced_tables = guard_select(
            sql, policy.readable_tables(), policy.default_row_limit
        )
    except SqlGuardError as e:
        return {"error_code": e.error_code, "message": e.message, "hint": e.hint}

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                rows = await asyncio.wait_for(
                    conn.fetch(safe_sql), timeout=policy.query_timeout_seconds
                )
    except TimeoutError:
        return {
            "error_code": "QUERY_TIMEOUT",
            "message": f"Query exceeded the {policy.query_timeout_seconds}s timeout.",
            "hint": "Add a more specific WHERE clause or a smaller LIMIT.",
        }
    except Exception as e:
        return {
            "error_code": "QUERY_FAILED",
            "message": str(e),
            "hint": "Check table/column names against list_tables/describe_table.",
        }

    pii_columns: set[str] = set()
    for table_name in referenced_tables:
        table_policy = policy.table(table_name)
        if table_policy:
            pii_columns |= set(table_policy.pii_columns)

    row_dicts = redact_rows([dict(r) for r in rows], pii_columns)
    return {
        "rows": row_dicts,
        "row_count": len(row_dicts),
        "truncated": len(row_dicts) >= limit,
    }
