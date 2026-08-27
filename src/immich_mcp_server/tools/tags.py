"""Tags: list, read, create, update (color), delete, tag and untag assets.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.fastmcp import Context

from ..app import mcp, _client

@mcp.tool()
async def list_tags(ctx: Context) -> str:
    """List all tags in the library. Use this to discover existing tags before creating
    new ones or to find a tag ID for tagging operations. Read-only.

    Returns: JSON with total count and tags array (each with id, name, color).
    """
    try:
        result = await _client(ctx).list_tags()
        return json.dumps({"total": len(result), "tags": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def get_tag(ctx: Context, tag_id: str) -> str:
    """Get details for a specific tag. Use this to inspect a tag's properties. Read-only.

    Args:
        tag_id: The tag's UUID (from list_tags).

    Returns: JSON with tag id, name, color, and usage count.
    """
    try:
        result = await _client(ctx).get_tag(tag_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def create_tag(ctx: Context, name: str, color: str = "") -> str:
    """Create a new tag for categorizing assets. Use list_tags first to avoid duplicates.
    Side effect: creates a new tag in Immich.

    Args:
        name: Tag display name (e.g. 'Vacation', 'Family', 'Work'). Must be unique.
        color: Optional hex color for the tag (e.g. '#FF5733').

    Returns: JSON with the new tag's id, name, and color.
    """
    try:
        result = await _client(ctx).create_tag(name, color=color or None)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def update_tag(ctx: Context, tag_id: str, name: str | None = None, color: str | None = None) -> str:
    """Update a tag's color. Side effect: changes apply to all assets using this tag.
    Immich's API cannot rename a tag (TagUpdateDto only carries `color`); to rename,
    create_tag with the new name, tag_assets, then delete_tag the old one.

    Args:
        tag_id: The tag's UUID.
        name: Not supported by Immich — passing it returns an error explaining the workaround.
        color: New hex color (e.g. '#FF5733'). Omit to keep current.

    Returns: JSON with the updated tag object.
    """
    if name is not None:
        return json.dumps({
            "error": "Immich's API cannot rename a tag (only its color can change). "
                     "To rename: create_tag with the new name, tag_assets the same assets, "
                     "then delete_tag the old tag."
        })
    fields: dict = {}
    if color is not None:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide color."})
    try:
        result = await _client(ctx).update_tag(tag_id, **fields)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def delete_tag(ctx: Context, tag_id: str) -> str:
    """Delete a tag and remove it from all assets. The assets themselves are unaffected.
    Side effect: permanently deletes the tag (cannot be undone).

    Args:
        tag_id: The tag's UUID to delete.

    Returns: JSON with deleted confirmation and tag_id.
    """
    try:
        await _client(ctx).delete_tag(tag_id)
        return json.dumps({"deleted": True, "tag_id": tag_id})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def tag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Apply a tag to multiple assets at once. Use this to bulk-categorize photos
    (e.g. tag all vacation photos). Side effect: adds tag association to assets.

    Args:
        tag_id: The tag UUID to apply (from list_tags or create_tag).
        asset_ids: List of asset UUIDs to tag. Must not be empty.

    Returns: JSON with tag_id, count tagged, and per-asset results.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).tag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "tagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def untag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Remove a tag from multiple assets. The tag itself remains; only the association is
    removed. Side effect: removes tag-to-asset links.

    Args:
        tag_id: The tag UUID to remove from assets.
        asset_ids: List of asset UUIDs to untag. Must not be empty.

    Returns: JSON with tag_id, count untagged, and per-asset results.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).untag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "untagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})
