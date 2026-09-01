"""
Keeps tool_manifest.TOOL_NAMES in lockstep with what the server registers.

Every era-compatibility check asserts against the manifest, so the manifest
itself must never drift from the real tool surface: this is the one test that
fails when a tool is added or removed without updating the manifest.
"""

import pytest

# Importing server registers every tool module on the shared app.
from immich_mcp_server import server  # noqa: F401
from immich_mcp_server.app import mcp

from tool_manifest import TOOL_NAMES


@pytest.mark.asyncio
async def test_manifest_matches_the_registered_tools():
    registered = sorted(tool.name for tool in await mcp.list_tools())

    assert registered == sorted(TOOL_NAMES)


def test_manifest_is_sorted_and_unique():
    assert list(TOOL_NAMES) == sorted(set(TOOL_NAMES))
