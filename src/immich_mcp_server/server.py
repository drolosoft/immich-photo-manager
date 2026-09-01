"""
Immich MCP Server — Photo management tools for Claude.

Part of the immich-photo-manager plugin.
License: MIT

The MCPServer app lives in `app.py`; every tool module under `tools/` registers
its tools on import. This module wires them together and re-exports the tool
functions (tests and scripts call them as `server.<tool>`).
"""

from .app import app_lifespan, mcp, _client, _transport_security  # noqa: F401
from .tools import (
    health,
    credentials,
    assets,
    search,
    albums,
    thumbnails,
    images,
    video,
    sharing,
    people,
    trash,
    duplicates,
    tags,
    upload,
    asset_list,
    export,
    memories,
    timeline,
)
from .tools._common import _album_assets, _entry_to_image, _image_format_from_mime  # noqa: F401

_TOOL_MODULES = (
    health, credentials, assets, search, albums, thumbnails, images, video,
    sharing, people, trash, duplicates, tags, upload, asset_list, export,
    memories, timeline,
)

# Re-export every tool function as `server.<name>` (tests and the live harness use it).
for _module in _TOOL_MODULES:
    for _name, _obj in vars(_module).items():
        if callable(_obj) and getattr(_obj, "__module__", None) == _module.__name__:
            globals()[_name] = _obj
del _module, _name, _obj

# ── HTTP App (for Streamable HTTP transport) ────────────────
#
# Served by uvicorn from __main__ (see MCP_HOST/MCP_PORT there). The SDK
# serves both protocol eras from this one app: legacy `initialize` clients and
# stateless 2026-07-28 clients.

app = mcp.streamable_http_app(transport_security=_transport_security)
