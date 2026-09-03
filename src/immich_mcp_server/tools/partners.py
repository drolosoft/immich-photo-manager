"""Partners: share the whole library with another user on the same server.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error


@mcp.tool()
async def list_users(ctx: Context) -> str:
    """The users visible on this Immich server. Use this to find the id that
    create_partner needs, or to see who could be shared with. Read-only.

    Returns: JSON with total and a users array of {id, name, email}.
    """
    result = await _client(ctx).list_users()
    users = [{"id": user.get("id"), "name": user.get("name"), "email": user.get("email")}
             for user in result]
    return json.dumps({"total": len(users), "users": users}, default=str)


@mcp.tool()
async def list_partners(ctx: Context) -> str:
    """Who shares their library with this account, and who this account shares
    with. Partner sharing is Immich's family feature: each side keeps its own
    library but can see the other's. Read-only.

    Returns: JSON with shared_with_me and shared_by_me arrays
    (id, name, email, in_timeline).
    """
    def trim(partner):
        return {"id": partner.get("id"), "name": partner.get("name"),
                "email": partner.get("email"), "in_timeline": partner.get("inTimeline")}

    # Immich answers one direction per request; both together are the useful view.
    shared_with_me = await _client(ctx).list_partners("shared-with")
    shared_by_me = await _client(ctx).list_partners("shared-by")
    return json.dumps({
        "shared_with_me": [trim(partner) for partner in shared_with_me],
        "shared_by_me": [trim(partner) for partner in shared_by_me],
    }, default=str)


@mcp.tool()
async def create_partner(ctx: Context, user_id: str) -> str:
    """Share this account's library with another user on the server. The other
    user will see these photos next to their own. Find the id with list_users.
    Side effect: grants the user read access to the whole library.

    Args:
        user_id: The user to share with.

    Returns: JSON with the new partner entry.
    """
    # Immich answers 400 for this account's own id and for a user who is already
    # a partner; both are worth telling apart from a broken call.
    try:
        result = await _client(ctx).create_partner(user_id)
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    return json.dumps({"id": result.get("id"), "in_timeline": result.get("inTimeline")},
                      default=str)


@mcp.tool()
async def update_partner(ctx: Context, user_id: str, in_timeline: bool) -> str:
    """Show or hide a partner's photos inside the main timeline (they stay
    reachable either way). Only works on a partner who shares their library
    with this account (someone in shared_with_me), because the flag controls
    how THEIR photos appear in THIS timeline. Side effect: updates the setting
    on the server.

    Args:
        user_id: The partner whose setting changes.
        in_timeline: True to mix their photos into the timeline, false to keep
            them separate.

    Returns: JSON with the updated partner entry.
    """
    try:
        result = await _client(ctx).update_partner(user_id, in_timeline=in_timeline)
    except httpx.HTTPStatusError as exc:
        # Immich answers 400 or 404 for a partner this account shares WITH, which
        # is the mistake this tool invites, so the status carries the way out too.
        error = json.loads(_api_error(exc))
        error["hint"] = (
            "in_timeline only applies to a partner who shares their library with "
            "this account: pass an id from the shared_with_me list of list_partners, "
            "not from shared_by_me."
        )
        return json.dumps(error)

    return json.dumps({"id": result.get("id"), "in_timeline": result.get("inTimeline")},
                      default=str)


@mcp.tool()
async def remove_partner(ctx: Context, user_id: str) -> str:
    """Stop sharing this account's library with a user. Their own photos are not
    touched. Side effect: revokes their access.

    Args:
        user_id: The user to unshare with.

    Returns: JSON confirming the removal.
    """
    await _client(ctx).remove_partner(user_id)
    return json.dumps({"success": True, "removed": user_id})
