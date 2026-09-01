"""Health and library statistics: ping, server version, counts.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client

@mcp.tool()
async def ping(ctx: Context) -> str:
    """Check Immich server connectivity. Use this to verify the server is reachable
    before running other operations. Read-only.

    Returns: JSON with 'server' status ('pong' if healthy).
    """
    result = await _client(ctx).ping()
    return json.dumps(result)


@mcp.tool()
async def get_server_version(ctx: Context) -> str:
    """Get the Immich server version. Use this to check compatibility or report
    the running server version. Read-only.

    Returns: JSON with major, minor, and patch version numbers.
    """
    result = await _client(ctx).get_server_version()
    return json.dumps(result)


@mcp.tool()
async def get_statistics(ctx: Context) -> str:
    """Get library statistics. Use this for a quick overview of library size
    without listing individual assets. Read-only.

    Returns: JSON with total photo count, video count, and storage usage in bytes.
    """
    result = await _client(ctx).get_statistics()
    return json.dumps(result)
