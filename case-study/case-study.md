# Guarded Postgres MCP Server: Let Claude Query Your Database Without Fear of `DROP TABLE`

**Role:** AI Automation Engineer and Claude Expert
**Stack:** Python, MCP (Model Context Protocol), FastMCP/MCPServer, Postgres, asyncpg, sqlglot, Pydantic
**Type:** Reference build and demonstration (portfolio project, not a paid engagement)

## The problem

Connecting Claude to a company's live Postgres database is one of the most-requested
AI automation jobs — and one of the most dangerous. The moment Claude can *execute*
SQL, three things can go wrong, all quietly:

1. **Destruction.** A confused model, or a user pasting a "helpful" query, runs
   `DROP TABLE`, `DELETE`, or a stacked-statement injection — and the data is gone.
2. **Leakage.** Claude happily returns a full column of emails, phone numbers, or
   card data because nobody told it those were off-limits.
3. **Silent wrong answers.** A query returns the wrong shape or a truncated result,
   Claude reports it as fact, and no one notices until a decision was already made on
   bad numbers.

Most "connect Claude to your DB" demos ignore all three because they demo on the
happy path. This build is designed against the failure path.

## What I built

A **Model Context Protocol server** that gives Claude *governed* access to Postgres.
Claude gets read-mostly access with a small set of safe write actions — and every
call passes through an explicit chain of guards before it ever reaches the database.

```
Claude Desktop / API  ──MCP (stdio)──▶  Guarded MCP Server (Python)  ──▶  Postgres
                                        │                                  ▲
        Auth → Rate-limit → Schema-validate → SQL-guard →                  │
        PII-redact → Audit-log                                    least-privilege role
                                        │
                                    policy.yaml  (the single source of truth:
                                    which tables/columns, read vs write,
                                    row limits, which columns are PII)
```

The key design decision: **every guardrail is driven by one `policy.yaml` file, not
hard-coded.** To point this server at a different client's database, you edit that
file — you don't touch the code. That's what makes it a reusable product rather than
a one-off script.

## The tools Claude sees

| Tool | What it does | Guardrail |
|---|---|---|
| `list_tables` | Lists allow-listed tables | Only tables in `policy.yaml` |
| `describe_table` | Schema + a 3-row sample | Allow-list; PII columns masked |
| `query` | Runs a `SELECT` | Single read-only SELECT, no comments, no DDL/DML (even in CTEs), allow-listed tables only, forced `LIMIT`, timeout, PII masked |
| `insert_record` | Adds a row | Writable tables/columns only, Pydantic-validated, dry-run by default, transactional |
| `update_record` | Changes one row | Same, **plus** must target exactly one row by primary key |
| `get_audit_log` | Shows recent tool activity | So the client can verify safety themselves |

## The reliability layer (why this is different)

The safety isn't one wall — it's **defense in depth**, layers that would each have to
fail independently:

- **Application SQL guard.** `query` is parsed into a syntax tree with `sqlglot` and
  rejected unless it's exactly one read-only `SELECT` — catching DDL/DML even when
  it's smuggled inside a CTE like `WITH x AS (DELETE ... RETURNING *) SELECT * FROM x`.
- **Least-privilege database roles.** The server never connects as a superuser. Reads
  use a role with `SELECT`-only grants; writes use a separate role that can `INSERT`
  and `UPDATE` allow-listed tables but *cannot* `DELETE`, `DROP`, or `ALTER` anything.
  So even a bug in the Python guard can't destroy data — the database itself refuses.
- **Policy-driven PII redaction.** Columns marked PII in `policy.yaml` are masked in
  every result.
- **Dry-run writes.** `insert_record`/`update_record` report what they *would* do and
  change nothing unless called again with `confirm=true`.
- **Structured errors, never stack traces.** Every rejection returns
  `{error_code, message, hint}` — Claude can explain the refusal cleanly instead of
  leaking internals or failing silently.
- **Full audit log.** Every call is recorded (tool, redacted args, rows, latency,
  outcome) to an append-only log the client can inspect.

## Results (measured against an adversarial test suite)

I wrote **19 adversarial attacks** — the things a careless or malicious caller would
actually try — and ran every one against the server. Each must be refused with the
correct structured error, and the database must be provably unchanged afterward.
Every number is reproducible with one command (`python scripts/run_adversarial.py`);
no API tokens required.

| Attack category | Examples | Attempts | Got through |
|---|---|---|---|
| DDL (destroy schema) | `DROP TABLE`, `TRUNCATE`, `ALTER` | 3 | **0** |
| DML (modify via read tool) | `DELETE`, `UPDATE`, `INSERT` through `query` | 3 | **0** |
| Injection | stacked statements, comment smuggling, CTE writes, `SELECT INTO` | 5 | **0** |
| Exfiltration | reading `pg_catalog`, `information_schema` | 2 | **0** |
| Write authorization | writing protected columns / read-only tables | 5 | **0** |
| Integrity | updating a non-existent row | 1 | **0** |
| **Total** | | **19** | **0** |

**Database intact after all 19 attacks:** row count unchanged (7 → 7), target table
still exists. **Block rate: 100%.**

## How to point it at your database (about 15 minutes)

1. `docker compose up -d` starts a demo Postgres, or set `DATABASE_URL` to your own.
2. Copy `policy.example.yaml` to `policy.yaml` and list your tables, columns, which
   are writable, and which are PII.
3. Create the two least-privilege roles (SQL provided in `seed/03_roles.sql`).
4. Register the server in Claude Desktop's config (one JSON block, provided).
5. Ask Claude a business question — watch it query safely, then watch it refuse a
   `DROP TABLE` with a clean, explained error.

## Honesty note

This is a **reference/demo build**, not a paid client engagement. The metrics come
from the self-built 19-attack adversarial suite and are fully reproducible from the
repo. No client names, logos, or data are implied.
