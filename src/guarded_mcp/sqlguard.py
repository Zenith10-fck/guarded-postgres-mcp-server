"""SQL guard: only a single read-only SELECT is ever allowed through the
`query` tool. This is defense in depth on top of the least-privilege
database role added in fase 2 -- even if this guard had a bug, the DB role
itself won't have permission to DROP/INSERT/UPDATE/ALTER anything.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Into,
)


class SqlGuardError(Exception):
    def __init__(self, error_code: str, message: str, hint: str):
        self.error_code = error_code
        self.message = message
        self.hint = hint
        super().__init__(message)


def guard_select(
    sql: str, allowed_tables: set[str], row_limit: int
) -> tuple[str, int, set[str]]:
    """Validate `sql` and return (safe_sql, applied_limit, referenced_tables).

    `referenced_tables` lets the caller union pii_columns across every
    table touched by a join before redacting the result.

    Raises SqlGuardError with a structured reason for anything other than
    exactly one read-only SELECT against allow-listed tables.
    """
    raw = sql.strip()

    if "--" in raw or "/*" in raw:
        raise SqlGuardError(
            "COMMENT_REJECTED",
            "SQL comments are not allowed in query().",
            "Remove any -- or /* */ comments and try again.",
        )

    try:
        statements = sqlglot.parse(raw, read="postgres")
    except Exception as e:
        raise SqlGuardError(
            "SQL_PARSE_ERROR",
            f"Could not parse SQL: {e}",
            "Check for typos or unsupported syntax.",
        ) from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlGuardError(
            "MULTI_STATEMENT_REJECTED",
            "Only a single SQL statement is allowed per query() call.",
            "Split multiple statements into separate query() calls.",
        )

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise SqlGuardError(
            "NON_SELECT_REJECTED",
            "Only SELECT statements are allowed in query().",
            "This tool is read-only. Use insert_record/update_record for writes.",
        )

    for forbidden_type in _FORBIDDEN_NODE_TYPES:
        if list(tree.find_all(forbidden_type)):
            raise SqlGuardError(
                "FORBIDDEN_CLAUSE",
                f"Disallowed SQL construct found: {forbidden_type.__name__}.",
                "Only plain read-only SELECT queries are permitted, "
                "including inside CTEs.",
            )

    referenced_tables = {t.name for t in tree.find_all(exp.Table)}
    disallowed = referenced_tables - allowed_tables
    if disallowed:
        raise SqlGuardError(
            "TABLE_NOT_ALLOWED",
            f"Query references tables outside the allow-list: {sorted(disallowed)}",
            f"Allowed tables: {sorted(allowed_tables)}",
        )

    # Always force the LIMIT down to the policy's row_limit, regardless of
    # what the caller asked for -- this is a hard ceiling, not a suggestion.
    tree.set("limit", None)
    tree = tree.limit(row_limit)

    return tree.sql(dialect="postgres"), row_limit, referenced_tables
