"""Run every adversarial attack and write results.json -- the reproducible
"X attacks, 0 succeeded" evidence table for the case-study.

Mirrors the honesty pattern of the sibling projects' measure.py /
scorer.py: run the whole suite, tally the outcome, fail loudly if any
attack slips through.

Run: python scripts/run_adversarial.py
(requires: docker compose up -d)
"""

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

# Make the project root importable so `tests.adversarial.attacks` resolves
# when this script is run directly (python scripts/run_adversarial.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guarded_mcp.db import get_pool
from guarded_mcp.tools.query import query
from guarded_mcp.tools.writes import insert_record, update_record
from tests.adversarial.attacks import ALL_ATTACKS

_TOOLS = {"query": query, "insert_record": insert_record, "update_record": update_record}
_OUT = Path(__file__).resolve().parent.parent / "results.json"


async def main() -> None:
    pool = await get_pool()
    rows_before = await pool.fetchval("select count(*) from leads")

    per_attack = []
    by_category: dict[str, dict] = defaultdict(lambda: {"attempted": 0, "blocked": 0})

    for name, category, tool, kwargs, expected in ALL_ATTACKS:
        result = await _TOOLS[tool](**kwargs)
        got = result.get("error_code") if isinstance(result, dict) else None
        blocked = got == expected
        by_category[category]["attempted"] += 1
        by_category[category]["blocked"] += int(blocked)
        per_attack.append(
            {
                "name": name,
                "category": category,
                "tool": tool,
                "expected_error": expected,
                "got_error": got,
                "blocked": blocked,
            }
        )

    rows_after = await pool.fetchval("select count(*) from leads")
    table_exists = await pool.fetchval(
        "select count(*) from information_schema.tables where table_name = 'leads'"
    ) == 1

    attempted = len(per_attack)
    blocked = sum(1 for a in per_attack if a["blocked"])
    succeeded = attempted - blocked
    db_intact = rows_before == rows_after and table_exists
    passed = succeeded == 0 and db_intact

    report = {
        "summary": {
            "attacks_attempted": attempted,
            "attacks_blocked": blocked,
            "attacks_succeeded": succeeded,
            "block_rate": round(blocked / attempted, 4),
            "db_rows_before": rows_before,
            "db_rows_after": rows_after,
            "target_table_still_exists": table_exists,
            "database_intact": db_intact,
            "passed": passed,
        },
        "by_category": {
            cat: {**v, "block_rate": round(v["blocked"] / v["attempted"], 4)}
            for cat, v in sorted(by_category.items())
        },
        "per_attack": per_attack,
    }

    _OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"\nWrote {_OUT.name}")

    if not passed:
        failed = [a["name"] for a in per_attack if not a["blocked"]]
        raise SystemExit(f"FAIL: {succeeded} attack(s) got through: {failed}")
    print(f"PASS: {attempted} attacks attempted, 0 succeeded, database intact.")


if __name__ == "__main__":
    asyncio.run(main())
