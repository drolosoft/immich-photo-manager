"""Every MCP tool must go out with a description.

FastMCP takes the description from the function's ``__doc__``. A docstring that
is built by concatenating strings is an expression, not a docstring, so
``__doc__`` is None and the client sees an empty description. That happened to
``get_video_frames`` in v1.7.0 and this test keeps it from happening again.
"""

import asyncio

from immich_mcp_server import server


def test_every_tool_has_a_description():
    tools = asyncio.run(server.mcp.list_tools())
    missing = sorted(tool.name for tool in tools if not (tool.description or "").strip())
    assert missing == [], f"tools published without a description: {missing}"


def test_video_tools_describe_the_confirmation_gate():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    for name in ("get_video_frames", "get_video_frames_json"):
        description = tools[name].description
        assert "confirm" in description and "12" in description, name
