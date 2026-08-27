"""Browse assets by status and type without a query.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.fastmcp import Context

from ..app import mcp, _client
from ._common import _api_error

@mcp.tool()
async def list_assets(
    ctx: Context,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    is_trashed: bool | None = None,
    asset_type: str = "",
    page: int = 1,
    size: int = 50,
) -> str:
    """List assets with simple filters (no search query needed). Use this to browse
    the library by status (favorites, archived, trashed) or type. For finding specific
    content, use search_metadata (structured) or search_smart (visual AI). Read-only.

    Args:
        is_favorite: true = only favorites, false = only non-favorites, omit = all.
        is_archived: true = only archived, false = only non-archived, omit = all.
        is_trashed: true = only trashed items; false/omit = active library (Immich never mixes both).
        asset_type: 'IMAGE' or 'VIDEO'. Omit for both.
        page: Page number, starting from 1 (default 1).
        size: Results per page (1-200, default 50).

    Returns: JSON with total count, current page, and assets array with IDs, filenames, dates, and types.
    """
    try:
        result = await _client(ctx).list_assets(
            is_favorite=is_favorite,
            is_archived=is_archived,
            is_trashed=is_trashed,
            asset_type=asset_type or None,
            page=page,
            size=min(size, 200),
        )
        assets = result.get("assets", {}).get("items", [])
        total = result.get("assets", {}).get("total", 0)
        return json.dumps({"total": total, "page": page, "assets": assets}, default=str)
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)
