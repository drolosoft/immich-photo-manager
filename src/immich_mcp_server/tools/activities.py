"""Activities: comments and likes on shared albums.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client


@mcp.tool()
async def list_activities(
    ctx: Context,
    album_id: str,
    asset_id: str = "",
    type: str = "",
) -> str:
    """Comments and likes on a shared album, newest context included. Use this to
    read what the people an album is shared with have said about it or about one
    of its photos. Read-only.

    Args:
        album_id: The album whose activity to read.
        asset_id: Only activity on this asset within the album.
        type: 'comment' or 'like'. Omit for both.

    Returns: JSON with an activities array (id, type, comment, asset_id, user name,
    created_at).
    """
    result = await _client(ctx).list_activities(
        album_id,
        asset_id=asset_id or None,
        activity_type=type or None,
    )

    activities = []
    for activity in result:
        activities.append({
            "id": activity.get("id"),
            "type": activity.get("type"),
            "comment": activity.get("comment"),
            "asset_id": activity.get("assetId"),
            "user": (activity.get("user") or {}).get("name"),
            "created_at": activity.get("createdAt"),
        })
    return json.dumps({"total": len(activities), "activities": activities}, default=str)


@mcp.tool()
async def create_activity(
    ctx: Context,
    album_id: str,
    comment: str = "",
    asset_id: str = "",
    like: bool = False,
) -> str:
    """Post a comment (or a like) on a shared album or on one asset in it.
    Side effect: the activity appears for everyone the album is shared with.

    Args:
        album_id: The album to comment on.
        comment: The comment text. Leave empty when sending a like.
        asset_id: Attach the comment/like to this asset instead of the album.
        like: True to send a like instead of a comment.

    Returns: JSON with the created activity's id and type.
    """
    result = await _client(ctx).create_activity(
        album_id,
        activity_type="like" if like else "comment",
        comment=comment or None,
        asset_id=asset_id or None,
    )
    return json.dumps({"id": result.get("id"), "type": result.get("type")}, default=str)


@mcp.tool()
async def delete_activity(ctx: Context, activity_id: str) -> str:
    """Remove one comment or like. Side effect: deletes it for everyone.

    Args:
        activity_id: The activity to remove (from list_activities).

    Returns: JSON confirming the deletion.
    """
    await _client(ctx).delete_activity(activity_id)
    return json.dumps({"success": True, "deleted": activity_id})
