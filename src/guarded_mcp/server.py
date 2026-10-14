"""Guarded Postgres MCP Server — entry point.

Registers every tool by importing the tool modules (each one attaches
itself to the shared `mcp` app from app.py via @mcp.tool()), then starts
the process. This file stays thin on purpose: policy allow-listing lives in
policy.py, SQL safety in sqlguard.py, and each tool's own logic in
tools/*.py.
"""

from guarded_mcp.app import mcp
from guarded_mcp.tools import audit, query, tables, writes  # noqa: F401 -- registers @mcp.tool()s


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
