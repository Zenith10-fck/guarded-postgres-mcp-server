"""Shared MCPServer instance.

Tool modules under guarded_mcp/tools/ import `mcp` from here and register
themselves with @mcp.tool() directly. server.py just imports the tool
modules (to trigger that registration) and starts the process -- this
avoids a circular import between "the app" and "the tools".
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("guarded-postgres-mcp")
