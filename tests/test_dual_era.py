"""The server must speak BOTH MCP eras from one process (dual-era).

MCP 2026-07-28 removed the initialize handshake; earlier clients (Claude
Desktop, Cowork, Claude Code today) still open with `initialize`. A server
that only speaks one era breaks the other side, so these tests drive the real
stdio server over the wire twice: once forcing the legacy handshake, once
pinning the modern 2026-07-28 revision. Both must see the same tools and be
able to call one.
"""

import json
import os
import sys

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

from tool_manifest import TOOL_NAMES

MODERN = "2026-07-28"
# Tools whose presence Claude clients depend on: JSON base64 thumbnails stay.
LOAD_BEARING_TOOLS = {
    "get_asset_thumbnail",
    "get_album_thumbnails",
    "get_thumbnails_batch",
    "get_asset_image",
    "get_album_images",
    "get_images_batch",
}


def _stdio_server():
    """Spawn the packaged server over stdio with dummy Immich credentials.

    Startup pings Immich and only warns on failure (to stderr), so an
    unreachable URL is fine: the JSON-RPC surface still comes up.
    """
    env = {
        **os.environ,
        "IMMICH_BASE_URL": "http://127.0.0.1:1",
        "IMMICH_API_KEY": "dummy-key-for-contract-tests",
        "PYTHONPATH": os.path.join(os.path.dirname(__file__), "..", "src"),
    }
    return stdio_client(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "immich_mcp_server", "--transport", "stdio"],
            env=env,
        )
    )


async def _exercise(mode):
    async with Client(_stdio_server(), mode=mode) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools.tools}
        result = await client.call_tool("get_connection_info", {})
        text = next(b.text for b in result.content if b.type == "text")
        return client.protocol_version, names, json.loads(text)


@pytest.mark.asyncio
async def test_legacy_client_initialize_handshake_still_works():
    version, names, info = await _exercise("legacy")

    assert version != MODERN, "legacy mode must negotiate a pre-2026 revision"
    assert set(names) == set(TOOL_NAMES)
    assert LOAD_BEARING_TOOLS <= names
    assert info["base_url"] == "http://127.0.0.1:1"


@pytest.mark.asyncio
async def test_modern_client_stateless_2026_07_28_works():
    version, names, info = await _exercise(MODERN)

    assert version == MODERN
    assert set(names) == set(TOOL_NAMES)
    assert LOAD_BEARING_TOOLS <= names
    assert info["base_url"] == "http://127.0.0.1:1"


@pytest.mark.asyncio
async def test_both_eras_expose_identical_tool_surface():
    _, legacy_names, _ = await _exercise("legacy")
    _, modern_names, _ = await _exercise(MODERN)

    assert legacy_names == modern_names
