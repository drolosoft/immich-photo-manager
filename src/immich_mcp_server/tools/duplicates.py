"""Duplicates: ML duplicate groups (optionally scoped to an album) and their resolution.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _album_assets

@mcp.tool()
async def get_duplicates(ctx: Context, album_id: str = "") -> str:
    """Get ML-detected duplicate asset groups (same image stored more than once). Use this
    to review potential duplicates before resolving them with resolve_duplicates. Requires
    Immich ML service. Note: "duplicates" means the same picture, not the same person —
    for people use get_album (assets[].people) or get_asset_faces. Read-only.

    Args:
        album_id: Optional. Restrict to groups that touch this album; each group then also
            reports which of its assets are inside/outside the album.

    Returns: JSON array of duplicate groups (each with duplicateId, assets array, and similarity scores).
    """
    client = _client(ctx)
    groups = await client.get_duplicates()
    if not album_id:
        return json.dumps(groups, default=str)
    album = await client.get_album(album_id)
    in_album = {asset["id"] for asset in await _album_assets(client, album_id, album)}
    out = []
    for group in groups:
        ids = [asset["id"] for asset in group.get("assets", [])]
        inside = [i for i in ids if i in in_album]
        if inside:
            out.append({**group, "inAlbum": inside, "outsideAlbum": [i for i in ids if i not in in_album]})
    return json.dumps(
        {"albumId": album_id, "albumName": album.get("albumName", ""), "groups": out,
         "note": "Groups fully inside the album have an empty outsideAlbum list."},
        default=str,
    )


@mcp.tool()
async def resolve_duplicates(ctx: Context, groups: list[dict]) -> str:
    """Resolve duplicate groups by choosing which assets to keep and which to trash.
    Use this after reviewing results from get_duplicates. Trashed assets can still be
    recovered via restore_assets. Side effect: moves rejected duplicates to trash.

    Args:
        groups: List of dicts, each with: duplicateId (from get_duplicates), assetIds (UUIDs to KEEP), trashIds (UUIDs to TRASH).

    Returns: JSON with count of resolved groups.
    """
    await _client(ctx).resolve_duplicates(groups)
    return json.dumps({
        "resolved": len(groups),
        "message": "Duplicate groups resolved. Trashed assets can be restored from trash.",
    })
