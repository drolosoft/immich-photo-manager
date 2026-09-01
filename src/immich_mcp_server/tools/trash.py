"""Trash: soft delete, empty, restore everything, restore selected assets.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client

@mcp.tool()
async def delete_assets(ctx: Context, asset_ids: list[str], force: bool = False) -> str:
    """Delete assets (soft-delete to trash or permanent). Use this to remove unwanted
    photos/videos. Default is soft-delete (recoverable via restore_assets). With force=true,
    deletion is PERMANENT and IRREVERSIBLE. Side effect: moves/deletes assets.

    Args:
        asset_ids: List of asset UUIDs to delete.
        force: false (default) = move to trash (recoverable). true = PERMANENTLY delete (no undo).

    Returns: JSON with count deleted and whether force was used.
    """
    await _client(ctx).delete_assets(asset_ids, force=force)
    return json.dumps({
        "deleted": len(asset_ids),
        "force": force,
        "warning": "Assets permanently deleted." if force else "Assets moved to trash. Use restore_assets to undo.",
    })


@mcp.tool()
async def empty_trash(ctx: Context) -> str:
    """Permanently delete ALL assets currently in trash. DESTRUCTIVE and IRREVERSIBLE.
    Use this only after confirming the user wants to purge all trashed items. For
    deleting specific assets, use delete_assets instead. Side effect: permanently
    destroys all trashed assets and frees storage.

    Returns: JSON with success confirmation.
    """
    await _client(ctx).empty_trash()
    return json.dumps({"success": True, "warning": "All trashed assets have been permanently deleted."})


@mcp.tool()
async def restore_trash(ctx: Context) -> str:
    """Restore ALL trashed assets back to the library. Use this to undo an accidental
    bulk deletion. For restoring specific assets only, use restore_assets instead.
    Side effect: moves all trashed assets back to the active library.

    Returns: JSON with success confirmation.
    """
    await _client(ctx).restore_trash()
    return json.dumps({"success": True, "message": "All trashed assets have been restored."})


@mcp.tool()
async def restore_assets(ctx: Context, asset_ids: list[str]) -> str:
    """Restore specific assets from trash back to the active library. Use this to
    selectively recover accidentally deleted photos. For restoring everything at once,
    use restore_trash instead. Side effect: moves specified assets out of trash.

    Args:
        asset_ids: List of asset UUIDs currently in trash to restore.

    Returns: JSON with count of restored assets.
    """
    await _client(ctx).restore_assets(asset_ids)
    return json.dumps({"restored": len(asset_ids)})
