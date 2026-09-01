"""
Pins the SDK surface this project touches directly, so a rename fails loudly.

The live harness reads CallToolResult.is_error and ImageContent.mime_type as
plain attributes; if a future SDK renames either, these assertions turn the
regression into a red test instead of a harness that reports success while
seeing no errors at all.
"""

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent


def test_call_tool_result_still_has_is_error():
    assert "is_error" in CallToolResult.model_fields


def test_image_content_still_has_mime_type():
    assert "mime_type" in ImageContent.model_fields


def test_mcpserver_accepts_a_version():
    server = MCPServer("contract-probe", version="9.9.9")

    assert server.version == "9.9.9"
