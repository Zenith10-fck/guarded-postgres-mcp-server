"""Adversarial tests: every attack in attacks.py must be refused with the
right structured error, and -- for destructive attacks -- the database must
be provably unchanged afterward.

Run:  pytest tests/adversarial/ -v
(requires: docker compose up -d)
"""

import pytest

from guarded_mcp.db import get_pool
from guarded_mcp.tools.query import query
from guarded_mcp.tools.writes import insert_record, update_record
from tests.adversarial.attacks import ALL_ATTACKS

pytestmark = pytest.mark.asyncio

_TOOLS = {"query": query, "insert_record": insert_record, "update_record": update_record}


@pytest.mark.parametrize("name,category,tool,kwargs,expected", ALL_ATTACKS, ids=[a[0] for a in ALL_ATTACKS])
async def test_attack_is_refused(name, category, tool, kwargs, expected):
    result = await _TOOLS[tool](**kwargs)
    assert isinstance(result, dict), f"{name}: expected a structured dict result"
    assert result.get("error_code") == expected, (
        f"{name}: expected error_code={expected}, got {result}"
    )


async def test_database_is_unchanged_after_all_attacks():
    """Defense-in-depth check: run every attack, then confirm the leads
    table's row count is exactly what it was before -- nothing was
    dropped, deleted, or inserted."""
    pool = await get_pool()
    before = await pool.fetchval("select count(*) from leads")

    for name, category, tool, kwargs, expected in ALL_ATTACKS:
        await _TOOLS[tool](**kwargs)

    after = await pool.fetchval("select count(*) from leads")
    assert after == before, f"row count changed: {before} -> {after}"

    # leads table still exists (wasn't dropped by any attack)
    still_exists = await pool.fetchval(
        "select count(*) from information_schema.tables where table_name = 'leads'"
    )
    assert still_exists == 1
