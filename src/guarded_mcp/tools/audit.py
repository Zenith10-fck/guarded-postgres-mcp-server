"""get_audit_log -- lets Claude (and therefore the client) inspect recent
tool activity. This is what turns "trust me, it's safe" into something a
client can actually verify for themselves.
"""

from guarded_mcp.app import mcp
from guarded_mcp.audit import audited, read_recent


@mcp.tool()
@audited("get_audit_log")
async def get_audit_log(limit: int = 20) -> list[dict]:
    """Return the most recent audit log entries (oldest first, newest last)."""
    return read_recent(limit)
