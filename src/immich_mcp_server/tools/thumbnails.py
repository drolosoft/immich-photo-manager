"""Thumbnails as base64 JSON, the format the HTML gallery skills embed as data: URIs.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client

@mcp.tool()
async def get_asset_thumbnail(ctx: Context, asset_id: str, size: str = "thumbnail") -> str:
    """Get a base64-encoded thumbnail image for a single asset. Use this to visually
    inspect one photo. For multiple photos, use get_thumbnails_batch (by IDs) or
    get_album_thumbnails (by album). Read-only.

    Args:
        asset_id: The asset's UUID.
        size: 'thumbnail' (250px, fast) or 'preview' (1440px, higher quality). Default: 'thumbnail'.

    Returns: JSON with 'data' (base64 string) and 'type' (MIME type, e.g. 'image/jpeg').
    """
    result = await _client(ctx).get_asset_thumbnail(asset_id, size)
    return json.dumps(result)


@mcp.tool()
async def get_album_thumbnails(
    ctx: Context, album_id: str, size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for photos in an album. Use this to generate visual
    HTML galleries from an existing album. For thumbnails from search results (no album),
    use get_thumbnails_batch instead. Read-only.

    Args:
        album_id: The album's UUID.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20).

    Returns: JSON with album info and thumbnails array (each with asset_id, base64 data, filename, date).
    """
    result = await _client(ctx).get_album_thumbnails(
        album_id, size, min(limit, 50)
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def get_thumbnails_batch(
    ctx: Context, asset_ids: list[str], size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for arbitrary asset IDs without needing an album.
    Use this to visually display search results or any ad-hoc set of photos. For album-based
    thumbnails, use get_album_thumbnails. For a single photo, use get_asset_thumbnail. Read-only.

    Args:
        asset_ids: List of asset UUIDs to fetch thumbnails for.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20). Only the first N IDs are fetched.

    Returns: JSON with thumbnails array (each with asset_id, base64 data, filename, date).
    """
    result = await _client(ctx).get_thumbnails_batch(
        asset_ids, size, min(limit, 50)
    )
    return json.dumps(result, default=str)
