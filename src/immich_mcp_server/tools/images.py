"""Thumbnails as MCP image blocks, for clients that render images inline.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""


from mcp.server.fastmcp import Context, Image

from ..app import mcp, _client
from ._common import _entry_to_image

@mcp.tool()
async def get_asset_image(ctx: Context, asset_id: str, size: str = "thumbnail") -> Image:
    """Get a single asset's thumbnail as an image block for inline visual display.
    Use this in clients that render images (Open WebUI, Claude Desktop). For HTML
    gallery generation with base64 data URIs (Cowork/skills), use get_asset_thumbnail
    instead — it returns JSON. Read-only.

    Args:
        asset_id: The asset's UUID.
        size: 'thumbnail' (250px, fast) or 'preview' (1440px, higher quality). Default: 'thumbnail'.

    Returns: An image block (MCP ImageContent) for visual display.
    """
    result = await _client(ctx).get_asset_thumbnail(asset_id, size)
    return _entry_to_image(result)


@mcp.tool(structured_output=False)
async def get_album_images(
    ctx: Context, album_id: str, size: str = "thumbnail", limit: int = 20
) -> list[Image]:
    """Get an album's thumbnails as image blocks for inline visual display. Use this
    to visually browse an album in clients that render images. For HTML gallery
    generation with base64 data URIs (Cowork/skills), use get_album_thumbnails
    instead — it returns JSON with filenames and dates. Read-only.

    Args:
        album_id: The album's UUID.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20).

    Returns: A list of image blocks suitable for visual display.
    """
    result = await _client(ctx).get_album_thumbnails(album_id, size, min(limit, 50))
    return [_entry_to_image(t) for t in result.get("thumbnails", [])]


@mcp.tool(structured_output=False)
async def get_images_batch(
    ctx: Context, asset_ids: list[str], size: str = "thumbnail", limit: int = 20
) -> list[Image]:
    """Get thumbnails for arbitrary asset IDs as image blocks for inline visual
    display. Use this to visually show search results in clients that render images.
    For HTML gallery generation with base64 data URIs (Cowork/skills), use
    get_thumbnails_batch instead — it returns JSON with filenames and dates. Read-only.

    Args:
        asset_ids: List of asset UUIDs to fetch thumbnails for.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20). Only the first N IDs are fetched.

    Returns: A list of image blocks suitable for visual display.
    """
    result = await _client(ctx).get_thumbnails_batch(asset_ids, size, min(limit, 50))
    return [_entry_to_image(t) for t in result.get("thumbnails", [])]
