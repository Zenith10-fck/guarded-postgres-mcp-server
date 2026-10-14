# Guarded Postgres MCP Server

An **MCP server** that lets Claude query and safely write to a Postgres database —
built so it **structurally cannot run `DROP TABLE`, leak PII, or silently return
wrong data**. Every guardrail is driven by one `policy.yaml` file, so the same server
works for any client's database by editing config, not code.

## Files

| Path | What it is |
|---|---|
| `policy.example.yaml` | The single source of truth: which tables/columns Claude may read or write, row limits, and which columns are PII. Copy to `policy.yaml` and edit per client. |
| `docker-compose.yml` | One-command demo Postgres, auto-seeded from `seed/`. |
| `seed/` | Demo schema (`leads`, `orders`, `invoices`), sample data, and the two least-privilege DB roles. |
| `src/guarded_mcp/server.py` | Entry point — registers the tools and starts the server. |
| `src/guarded_mcp/app.py` | The shared `MCPServer` instance. |
| `src/guarded_mcp/policy.py` | Loads and enforces `policy.yaml`. |
| `src/guarded_mcp/sqlguard.py` | Parses and validates `query` SQL — single read-only SELECT only. |
| `src/guarded_mcp/redact.py` | PII masking (column-precise + a regex safety net). |
| `src/guarded_mcp/audit.py` | Append-only audit log + the `@audited` decorator on every tool. |
| `src/guarded_mcp/ratelimit.py` | Per-tool token-bucket rate limiting. |
| `src/guarded_mcp/db.py` | Async connection pools for the read role and the write role. |
| `src/guarded_mcp/models.py` | Pydantic v2 schemas validating write-tool inputs. |
| `src/guarded_mcp/tools/` | The tools Claude calls: `list_tables`, `describe_table`, `query`, `insert_record`, `update_record`, `get_audit_log`. |
| `tests/adversarial/attacks.py` | The attack catalog — single source of truth for the suite and the report. |
| `tests/adversarial/test_attacks.py` | pytest suite: every attack must be refused and the DB must be unchanged. |
| `scripts/run_adversarial.py` | Runs every attack and writes `results.json` ("X attacks, 0 succeeded"). |
| `scripts/smoke_test.py` | Fast end-to-end check of all tools (normal + rejected cases). |
| `results.json` | Output of `run_adversarial.py` (the reproducible evidence table). |
| `claude_desktop_config.example.json` | Drop-in Claude Desktop config to connect over stdio. |
| `case-study/` | Portfolio copy (`case-study.md`) + a polished page (`case-study.html`). |

## Run it

```bash
docker compose up -d                 # start the demo Postgres (seeds itself)
python -m venv .venv && source .venv/Scripts/activate   # (Windows Git Bash)
pip install -r requirements.txt && pip install -e .
python scripts/smoke_test.py         # prove every tool works (normal + rejected)
```

## Reproduce the metrics

```bash
python scripts/run_adversarial.py    # writes results.json
pytest tests/adversarial/ -v         # the same attacks as a formal test suite
```

Current run — **19 adversarial attacks, 0 succeeded, database intact** (row count
unchanged, target table still present). Categories: DDL, DML-via-read-tool,
injection (stacked statements / comment smuggling / CTE writes), exfiltration, write
authorization, and integrity. Every number regenerates from the command above.

## Connect to Claude Desktop

See `claude_desktop_config.example.json`. The server speaks **stdio** (not HTTP), so
Claude Desktop launches it as a subprocess — there's no URL or port. Point
`DATABASE_URL`/`WRITE_DATABASE_URL` at your own Postgres and edit `policy.yaml` to
match your schema.

## Glossary

Terms introduced while building this, in plain language:

- **MCP (Model Context Protocol)** — the standard that lets Claude call your Python
  functions as "tools". You tag a function with `@mcp.tool()` and Claude can invoke it.
- **stdio transport** — Claude Desktop talks to this server over stdin/stdout (like
  two programs connected by a pipe), not over the network. Hence no URL/port.
- **`async`/`await`** — lets Python wait on slow I/O (a database round-trip) without
  freezing the whole program.
- **Connection pool** — a set of ready-to-use DB connections borrowed and returned,
  instead of opening a fresh (expensive) connection per request.
- **Allow-list vs deny-list** — allow-list = "only what's on the list is permitted"
  (the safe default: forget to list something and it's denied). Deny-list = "everything
  except the list". This server is allow-list throughout.
- **SQL parser / AST** — `sqlglot` turns SQL text into a tree a program can inspect,
  so we can detect a hidden `DROP` inside a complex query — not just string-match "DROP".
- **CTE (Common Table Expression)** — a `WITH x AS (...) SELECT ...` query. Postgres
  allows writes inside a CTE, so the guard checks there too.
- **Parameterized query** — passing values separately from the SQL text (`$1`, `$2`)
  so user data can never be parsed as SQL. The write tools use this throughout.
- **Least-privilege role** — a database user granted only the permissions it needs
  (`SELECT` for reads; `INSERT`/`UPDATE` on specific tables for writes) — never a
  superuser.
- **Defense in depth** — independent layers (app-level SQL guard *and* DB-level role
  grants) that must all fail for an attack to succeed.
- **Structured error** — a consistent `{error_code, message, hint}` shape returned on
  every failure, instead of a raw stack trace or a silent empty result.
- **Dry-run / confirm** — a write reports what it *would* do and changes nothing until
  called again with `confirm=true`.
- **Transaction + rollback** — a group of DB operations that either all succeed or all
  undo, so a half-written row can't be left behind.
- **Append-only log** — a log you only ever add to (never edit/delete), so the audit
  trail can be trusted.
- **Token bucket** — a rate-limit metaphor: a bucket of tokens refilled over time; each
  call spends one; empty bucket = request politely refused.
- **PII (Personally Identifiable Information)** — data identifying a person (email,
  phone). Masked in results based on `policy.yaml`.
- **Adversarial test** — a test that actively tries to break the system (attack it),
  proving the guards hold — stronger evidence than testing only the happy path.

## Honesty note

This is a **reference/demo build**, not a paid client engagement. Metrics come from
the self-built 19-attack adversarial suite and are fully reproducible. No client
names, logos, or data are implied.
