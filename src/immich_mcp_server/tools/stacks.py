"""Stacks: group near-identical shots (bursts, retries) under one cover asset.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error


def _trim_stack(stack: dict) -> dict:
    """Full asset objects are heavy; the model needs ids and filenames."""
    assets = stack.get("assets") or []
    return {
        "id": stack.get("id"),
        "primary_asset_id": stack.get("primaryAssetId"),
        "asset_count": len(assets),
        "assets": [
            {"asset_id": asset.get("id"), "filename": asset.get("originalFileName")}
            for asset in assets
        ],
    }


@mcp.tool()
async def create_stack(ctx: Context, asset_ids: list[str]) -> str:
    """Group near-identical assets (a burst, retries of the same shot) into one
    stack. The library then shows the stack as a single item fronted by its primary
    asset, which keeps every shot without the visual clutter — a gentler cleanup
    than deleting. The first id becomes the primary. Side effect: creates the
    stack on the server.

    Args:
        asset_ids: The assets to group, at least two. Order matters: the first is
            the cover.

    Returns: JSON with the new stack's id, primary_asset_id and asset list.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})

    # A single asset and an id that is not a real asset both answer 400; the
    # status names which of the two Immich objected to.
    try:
        result = await _client(ctx).create_stack(asset_ids)
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    return json.dumps(_trim_stack(result), default=str)


@mcp.tool()
async def list_stacks(ctx: Context, primary_asset_id: str = "") -> str:
    """List every stack in the library. Use this to see what is already grouped
    before creating new stacks or to find a stack's id. Read-only.

    Args:
        primary_asset_id: Only the stack fronted by this asset.

    Returns: JSON with total and a stacks array (id, primary_asset_id, assets).
    """
    result = await _client(ctx).list_stacks(primary_asset_id=primary_asset_id or None)
    stacks = [_trim_stack(stack) for stack in result]
    return json.dumps({"total": len(stacks), "stacks": stacks}, default=str)


@mcp.tool()
async def get_stack(ctx: Context, stack_id: str) -> str:
    """One stack with its assets. Use this after list_stacks to see everything a
    group holds before changing its cover or dissolving it, or to check what
    create_stack actually grouped. Read-only.

    Args:
        stack_id: The stack to fetch.

    Returns: JSON with id, primary_asset_id and the asset list.
    """
    result = await _client(ctx).get_stack(stack_id)
    return json.dumps(_trim_stack(result), default=str)


@mcp.tool()
async def update_stack(ctx: Context, stack_id: str, primary_asset_id: str) -> str:
    """Change which asset fronts a stack (the one the library shows). Side effect:
    updates the stack on the server.

    Args:
        stack_id: The stack to update.
        primary_asset_id: The asset that should become the cover. It must already
            belong to the stack.

    Returns: JSON with the updated stack.
    """
    result = await _client(ctx).update_stack(stack_id, primary_asset_id=primary_asset_id)
    return json.dumps(_trim_stack(result), default=str)


@mcp.tool()
async def delete_stack(ctx: Context, stack_id: str) -> str:
    """Dissolve a stack. The assets are NOT deleted — they simply show as
    individual items again. Side effect: removes the grouping on the server.

    Args:
        stack_id: The stack to dissolve.

    Returns: JSON confirming the deletion.
    """
    await _client(ctx).delete_stack(stack_id)
    return json.dumps({"success": True, "deleted": stack_id,
                       "note": "The assets stay in the library, only the grouping is gone."})
